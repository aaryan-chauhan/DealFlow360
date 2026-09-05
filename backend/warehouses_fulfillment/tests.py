"""Regression tests for the fulfillment split engine (§7.2) and the RBAC rules it shares
with quotations and approvals (§3, §12).

These are the behaviours that were reported broken and confirmed working; they are pinned
here so a future change cannot quietly undo them again.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Company, Customer, Membership, Role, User
from approvals.models import ApprovalRequest, ApprovalStep
from approvals.services import act_on_request, route_quotation
from audit_log.models import AuditEntry
from catalog.models import Product
from pricing_discounts.models import ApprovalChainRule, DiscountTier
from quotations.models import Quotation, QuotationLine

from .models import BackorderEvent, FulfillmentOrder, StockLevel, Warehouse
from .services import (
    accept_split,
    ensure_fulfillment_order,
    override_split,
    scan_backorder_replenishment,
)

D = Decimal


class FulfillmentTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Testco")
        roles = {r.code: r for r in Role.objects.all()}

        def member(email, role_code):
            user = User.objects.create_user(email=email, password="x")
            Membership.objects.create(
                user=user, company=cls.company, role=roles[role_code], is_active_default=True
            )
            return user

        cls.rep = member("rep@t.example", Role.SALES_REP)
        cls.other_rep = member("rep2@t.example", Role.SALES_REP)
        cls.manager = member("mgr@t.example", Role.SALES_MANAGER)
        cls.finance = member("fin@t.example", Role.FINANCE_OPS)
        cls.admin = member("admin@t.example", Role.ADMIN)

        cls.customer = Customer.objects.create(
            company=cls.company, name="Buyer Ltd", tier=Customer.BRONZE, email="b@t.example"
        )
        cls.widget = Product.objects.create(
            company=cls.company, name="Widget", category=Product.HARDWARE, base_price=D("100.00")
        )

        # Governance: Bronze may discount 5%; over 5 points of overage needs Finance too.
        DiscountTier.objects.create(company=cls.company, name="Bronze", max_discount_pct=D("5.00"))
        ApprovalChainRule.objects.create(
            company=cls.company,
            discount_range_from=D("0.00"),
            discount_range_to=D("5.00"),
            required_level=ApprovalChainRule.MANAGER,
        )
        ApprovalChainRule.objects.create(
            company=cls.company,
            discount_range_from=D("5.00"),
            discount_range_to=D("100.00"),
            required_level=ApprovalChainRule.MANAGER_THEN_FINANCE,
        )

        # Cheap site first, so the optimiser's ordering is deterministic.
        cls.mumbai = Warehouse.objects.create(
            company=cls.company, name="Mumbai WH", shipping_cost_weight=D("1.00")
        )
        cls.bangalore = Warehouse.objects.create(
            company=cls.company, name="Bangalore WH", shipping_cost_weight=D("2.00")
        )

    def stock(self, warehouse, qty):
        level, _ = StockLevel.objects.get_or_create(warehouse=warehouse, product=self.widget)
        level.qty_on_hand = D(qty)
        level.save()
        return level

    def quote(self, owner, qty, discount="0.00"):
        quotation = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=owner
        )
        QuotationLine.objects.create(
            quotation=quotation,
            product=self.widget,
            qty=D(qty),
            unit_price=D("100.00"),
            discount_pct=D(discount),
        )
        return quotation

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


class OwnerScopingTests(FulfillmentTestBase):
    """§12: only a Sales Rep is owner-filtered. Every other role sees the whole company."""

    def setUp(self):
        self.stock(self.mumbai, 100)
        self.stock(self.bangalore, 100)
        for owner in (self.rep, self.other_rep, self.admin):
            quotation = self.quote(owner, 5)
            quotation.status = Quotation.APPROVED
            quotation.save(update_fields=["status"])
            ensure_fulfillment_order(quotation)

    def visible_to(self, user):
        response = self.client_for(user).get("/api/fulfillment/orders")
        self.assertEqual(response.status_code, 200)
        return {row["quotation_number"] for row in response.json()}

    def test_finance_sees_every_order_whatever_the_owner(self):
        self.assertEqual(len(self.visible_to(self.finance)), 3)

    def test_admin_and_manager_see_every_order(self):
        self.assertEqual(len(self.visible_to(self.admin)), 3)
        self.assertEqual(len(self.visible_to(self.manager)), 3)

    def test_sales_rep_sees_only_their_own(self):
        visible = self.visible_to(self.rep)
        self.assertEqual(len(visible), 1)
        owned = Quotation.objects.get(owner=self.rep).number
        self.assertEqual(visible, {owned})


class ApprovalStageTests(FulfillmentTestBase):
    """§12: an action is validated against the *current* pending step, not "any manager"."""

    def setUp(self):
        # 25% against a 5% ceiling = 20 points over -> manager, then finance.
        self.quotation = self.quote(self.rep, 4, discount="25.00")
        _, self.request = route_quotation(self.quotation, self.rep)
        self.assertEqual(self.request.required_level, "manager_then_finance")

    def test_finance_cannot_act_while_the_manager_step_is_pending(self):
        self.assertEqual(self.request.current_step.stage, ApprovalStep.MANAGER)
        response = self.client_for(self.finance).post(
            f"/api/approvals/{self.request.id}/approve", {"reason": "too early"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ApprovalRequest.PENDING)

    def test_chain_advances_to_finance_once_the_manager_approves(self):
        act_on_request(
            self.request, self.manager, self.manager.memberships.first(), ApprovalStep.APPROVED
        )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ApprovalRequest.PENDING)
        self.assertEqual(self.request.current_step.stage, ApprovalStep.FINANCE)

    def test_finance_can_approve_once_it_is_their_turn(self):
        act_on_request(
            self.request, self.manager, self.manager.memberships.first(), ApprovalStep.APPROVED
        )
        response = self.client_for(self.finance).post(
            f"/api/approvals/{self.request.id}/approve", {"reason": "finance ok"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.request.refresh_from_db()
        self.quotation.refresh_from_db()
        self.assertEqual(self.request.status, ApprovalRequest.APPROVED)
        self.assertEqual(self.quotation.status, Quotation.APPROVED)

        finance_step = self.request.steps.get(stage=ApprovalStep.FINANCE)
        self.assertEqual(finance_step.reviewer, self.finance)
        self.assertTrue(
            AuditEntry.objects.filter(
                object_id=self.quotation.id, action="approval_approved", user=self.finance
            ).exists()
        )

    def test_manager_cannot_act_on_the_finance_step(self):
        """The stage guard has to bite in both directions, not just against Finance."""
        act_on_request(
            self.request, self.manager, self.manager.memberships.first(), ApprovalStep.APPROVED
        )
        response = self.client_for(self.manager).post(
            f"/api/approvals/{self.request.id}/approve", {"reason": "again"}, format="json"
        )
        self.assertEqual(response.status_code, 403)


class AutoCreationTests(FulfillmentTestBase):
    def test_approval_opens_a_fulfillment_order_with_a_split(self):
        self.stock(self.mumbai, 10)
        self.stock(self.bangalore, 10)
        quotation = self.quote(self.rep, 15)

        # The trigger defers to on_commit, which a TestCase would otherwise swallow.
        with self.captureOnCommitCallbacks(execute=True):
            quotation.set_status(Quotation.APPROVED, self.rep)

        order = FulfillmentOrder.objects.get(quotation=quotation)
        self.assertEqual(order.status, FulfillmentOrder.SUGGESTED)
        allocated = {
            line.warehouse.name: line.qty_fulfilled
            for line in order.split_lines.filter(is_backorder=False)
        }
        self.assertEqual(allocated, {"Mumbai WH": D("10.00"), "Bangalore WH": D("5.00")})
        self.assertFalse(order.has_backorder)


class SplitEngineTests(FulfillmentTestBase):
    def test_single_warehouse_is_preferred_over_a_cheaper_split(self):
        self.stock(self.mumbai, 3)
        self.stock(self.bangalore, 20)
        order = self.approved_order(10)
        lines = list(order.split_lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].warehouse, self.bangalore)

    def test_shortfall_becomes_a_backorder_line_and_opens_an_event(self):
        self.stock(self.mumbai, 7)
        self.stock(self.bangalore, 5)
        order = self.approved_order(20)
        backorder = order.split_lines.get(is_backorder=True)
        self.assertEqual(backorder.qty_fulfilled, D("8.00"))
        self.assertTrue(order.has_backorder)
        self.assertTrue(
            BackorderEvent.objects.filter(fulfillment_order=order, resolved=False).exists()
        )

    def approved_order(self, qty):
        quotation = self.quote(self.rep, qty)
        quotation.status = Quotation.APPROVED
        quotation.save(update_fields=["status"])
        return ensure_fulfillment_order(quotation)


class OverrideTests(FulfillmentTestBase):
    def setUp(self):
        self.stock(self.mumbai, 7)
        self.stock(self.bangalore, 5)
        quotation = self.quote(self.rep, 12)
        quotation.status = Quotation.APPROVED
        quotation.save(update_fields=["status"])
        self.order = ensure_fulfillment_order(quotation)

    def test_override_beyond_available_stock_is_rejected(self):
        response = self.client_for(self.finance).post(
            f"/api/fulfillment/{self.order.id}/override",
            {
                "lines": [
                    {
                        "product": str(self.widget.id),
                        "warehouse": str(self.mumbai.id),
                        "qty": "12",
                    }
                ],
                "reason": "oversell",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot oversell", str(response.json()))

    def test_a_rejected_override_leaves_the_split_untouched(self):
        before = {
            (line.warehouse_id, line.is_backorder): line.qty_fulfilled
            for line in self.order.split_lines.all()
        }
        with self.assertRaises(Exception):
            override_split(
                self.order,
                self.finance,
                [{"warehouse": self.mumbai, "product": self.widget, "qty": D("12")}],
            )
        after = {
            (line.warehouse_id, line.is_backorder): line.qty_fulfilled
            for line in self.order.split_lines.all()
        }
        self.assertEqual(before, after)

    def test_sales_rep_cannot_override(self):
        response = self.client_for(self.rep).post(
            f"/api/fulfillment/{self.order.id}/override",
            {"lines": [{"product": str(self.widget.id), "warehouse": str(self.mumbai.id), "qty": "1"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class ReplenishmentScanTests(FulfillmentTestBase):
    """The watcher must read live stock, and must not mistake the order's own unreserved
    allocation for spare stock (§7.2.6)."""

    def setUp(self):
        self.mumbai_stock = self.stock(self.mumbai, 7)
        self.stock(self.bangalore, 5)
        quotation = self.quote(self.rep, 20)
        quotation.status = Quotation.APPROVED
        quotation.save(update_fields=["status"])
        self.order = ensure_fulfillment_order(quotation)
        self.backorder = self.order.split_lines.get(is_backorder=True)

    def flag(self):
        scan_backorder_replenishment(company=self.company)
        self.backorder.refresh_from_db()
        return self.backorder.consolidation_available

    def test_a_genuine_shortfall_is_not_flagged_on_a_suggested_order(self):
        # Mumbai's 7 free units are the ones this order already plans to ship.
        self.assertFalse(self.flag())

    def test_restock_is_detected_on_a_suggested_order(self):
        self.mumbai_stock.qty_on_hand = D("15")
        self.mumbai_stock.save()
        self.assertTrue(self.flag())

    def test_restock_is_detected_on_an_accepted_order(self):
        accept_split(self.order, self.finance)
        self.assertFalse(self.flag())
        self.mumbai_stock.refresh_from_db()
        self.mumbai_stock.qty_on_hand = D("15")
        self.mumbai_stock.save()
        self.assertTrue(self.flag())

    def test_flagging_never_applies_the_consolidation_by_itself(self):
        self.mumbai_stock.qty_on_hand = D("15")
        self.mumbai_stock.save()
        self.assertTrue(self.flag())
        self.assertTrue(self.backorder.is_backorder)
        self.assertIsNotNone(self.order.open_backorder_event)


class LineMergeTests(FulfillmentTestBase):
    """Adding a product already on the quote tops up that line (one row per product)."""

    def test_adding_the_same_product_twice_merges_into_one_line(self):
        quotation = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=self.rep
        )
        client = self.client_for(self.rep)
        url = f"/api/quotations/{quotation.id}/lines"

        first = client.post(
            url, {"product": str(self.widget.id), "qty": "3", "discount_pct": "12.00"}, format="json"
        )
        self.assertEqual(first.status_code, 201)

        second = client.post(
            url, {"product": str(self.widget.id), "qty": "12", "discount_pct": "0.00"}, format="json"
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["line"]["merged"])

        lines = list(quotation.lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].qty, D("15.00"))
        # The negotiated discount survives the top-up; the picker's default 0 must not
        # silently wipe it.
        self.assertEqual(lines[0].discount_pct, D("12.00"))


class WarehouseAdminEndpointTests(FulfillmentTestBase):
    """`/api/warehouses` and `/api/stock-levels` (Screen 18-adjacent admin config, §8).

    `WarehouseAdminViewSet`/`StockLevelAdminViewSet` reference `Warehouse`/`StockLevel`
    directly in `get_queryset` — pinned here because those names were once missing from
    this module's imports, which only surfaces as a 500 the moment the endpoint is hit
    (`manage.py check` cannot catch a NameError inside a method body).
    """

    def setUp(self):
        self.stock(self.mumbai, 40)

    def test_list_warehouses_does_not_crash(self):
        response = self.client_for(self.admin).get("/api/warehouses")
        self.assertEqual(response.status_code, 200)
        names = {w["name"] for w in response.json()}
        self.assertEqual(names, {"Mumbai WH", "Bangalore WH"})

    def test_list_stock_levels_does_not_crash(self):
        response = self.client_for(self.finance).get("/api/stock-levels")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["warehouse_name"], "Mumbai WH")

    def test_finance_can_create_warehouse(self):
        response = self.client_for(self.finance).post(
            "/api/warehouses",
            {"name": "Pune WH", "shipping_cost_weight": "1.50"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_rep_cannot_create_warehouse(self):
        response = self.client_for(self.rep).post(
            "/api/warehouses",
            {"name": "Rep's WH", "shipping_cost_weight": "1.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_rep_cannot_delete_warehouse(self):
        response = self.client_for(self.rep).delete(f"/api/warehouses/{self.mumbai.id}")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Warehouse.objects.filter(pk=self.mumbai.id).exists())

    def test_finance_can_update_stock_level(self):
        level = StockLevel.objects.get(warehouse=self.mumbai, product=self.widget)
        response = self.client_for(self.finance).patch(
            f"/api/stock-levels/{level.id}", {"qty_on_hand": "55"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        level.refresh_from_db()
        self.assertEqual(level.qty_on_hand, D("55"))

    def test_rep_cannot_update_stock_level(self):
        level = StockLevel.objects.get(warehouse=self.mumbai, product=self.widget)
        response = self.client_for(self.rep).patch(
            f"/api/stock-levels/{level.id}", {"qty_on_hand": "999"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
