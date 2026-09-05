"""Tests for the customer portal (§5.9) and the counter-offer -> re-approval loop (§11).

Two things are pinned here and both are load-bearing:

1. The token boundary. A portal token must open exactly one quotation, never a second one,
   and never any internal endpoint. These are the tests that would fail first if someone
   later "simplified" portal auth into the normal DRF authentication stack.
2. The governance loop. A customer counter-offer runs through the *same* risk engine a rep
   edit does — so an over-ceiling discount cannot be laundered through the portal.
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Company, Customer, Membership, Role, User
from approvals.models import ApprovalRequest, ApprovalStep
from approvals.services import act_on_request
from audit_log.models import AuditEntry
from catalog.models import Product
from pricing_discounts.models import ApprovalChainRule, CategoryDiscountCeiling, DiscountTier
from quotations.models import Quotation, QuotationLine

from .models import NegotiationMessage, PortalSession
from .services import PortalAccessDenied, issue_session, resolve_token

D = Decimal


class PortalTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Testco")
        roles = {r.code: r for r in Role.objects.all()}

        def member(email, role_code):
            user = User.objects.create_user(email=email, password="x")
            Membership.objects.create(
                user=user,
                company=cls.company,
                role=roles[role_code],
                is_active_default=True,
            )
            return user

        cls.rep = member("rep@test.com", Role.SALES_REP)
        cls.manager = member("mgr@test.com", Role.SALES_MANAGER)

        # Gold: 15% overall, but Services capped at 10% — the pair that makes a blended
        # score meaningfully different from a per-line one.
        tier = DiscountTier.objects.create(
            company=cls.company, name="Gold", max_discount_pct=D("15.00")
        )
        CategoryDiscountCeiling.objects.create(
            discount_tier=tier, category=Product.HARDWARE, max_discount_pct=D("15.00")
        )
        CategoryDiscountCeiling.objects.create(
            discount_tier=tier, category=Product.SERVICES, max_discount_pct=D("10.00")
        )
        ApprovalChainRule.objects.create(
            company=cls.company,
            discount_range_from=D("0.00"),
            discount_range_to=D("10.00"),
            required_level=ApprovalChainRule.MANAGER,
        )
        ApprovalChainRule.objects.create(
            company=cls.company,
            discount_range_from=D("10.00"),
            discount_range_to=D("100.00"),
            required_level=ApprovalChainRule.MANAGER_THEN_FINANCE,
        )

        cls.customer = Customer.objects.create(
            company=cls.company, name="Buyer Co", tier=Customer.GOLD, email="buy@test.com"
        )
        cls.other_customer = Customer.objects.create(
            company=cls.company, name="Rival Co", tier=Customer.GOLD, email="rival@test.com"
        )
        cls.laptop = Product.objects.create(
            company=cls.company,
            name="Laptop",
            category=Product.HARDWARE,
            base_price=D("1000.00"),
        )
        cls.warranty = Product.objects.create(
            company=cls.company,
            name="Warranty",
            category=Product.SERVICES,
            base_price=D("100.00"),
        )

    def make_quotation(self, customer=None, status=Quotation.APPROVED, discounts=("10", "5")):
        quotation = Quotation.objects.create(
            company=self.company, customer=customer or self.customer, owner=self.rep
        )
        QuotationLine.objects.create(
            quotation=quotation,
            product=self.laptop,
            qty=D("10"),
            unit_price=D("1000.00"),
            discount_pct=D(discounts[0]),
        )
        QuotationLine.objects.create(
            quotation=quotation,
            product=self.warranty,
            qty=D("10"),
            unit_price=D("100.00"),
            discount_pct=D(discounts[1]),
        )
        quotation.status = status
        quotation.save(update_fields=["status"])
        return quotation

    def portal_client(self):
        """A bare client with no credentials at all — the portal's real caller."""
        return APIClient()


class TokenScopeTests(PortalTestBase):
    """§5.9: the token is valid for exactly one (quotation, customer) pair, forever."""

    def test_valid_token_opens_only_its_own_quotation(self):
        mine = self.make_quotation()
        theirs = self.make_quotation(customer=self.other_customer)
        _, token = issue_session(mine, self.rep)

        response = self.portal_client().get(f"/api/portal/quotations/{token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quotation"]["number"], mine.number)
        self.assertNotEqual(response.json()["quotation"]["id"], str(theirs.id))

    def test_tampered_token_is_rejected(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        for mutated in (token[:-1] + "X", token.replace(":", "_", 1), "not-a-token"):
            response = self.portal_client().get(f"/api/portal/quotations/{mutated}")
            self.assertEqual(response.status_code, 401, mutated)

    def test_token_cannot_be_pointed_at_another_quotation(self):
        """The confused-deputy attempt: a real token, a different quotation id."""
        mine = self.make_quotation()
        theirs = self.make_quotation(customer=self.other_customer)
        _, token = issue_session(mine, self.rep)

        response = self.portal_client().post(
            f"/api/portal/{token}/comment",
            {"body": "hello", "quotation": str(theirs.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "scope_mismatch")

    def test_counter_offer_cannot_target_a_foreign_line(self):
        mine = self.make_quotation()
        theirs = self.make_quotation(customer=self.other_customer)
        foreign_line = theirs.lines.first()
        _, token = issue_session(mine, self.rep)

        response = self.portal_client().post(
            f"/api/portal/{token}/counter-offer",
            {"counter_discount_pct": "40", "quotation_line": str(foreign_line.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        foreign_line.refresh_from_db()
        self.assertEqual(foreign_line.discount_pct, D("10.00"))

    def test_portal_token_is_not_an_internal_credential(self):
        """A portal token in an Authorization header buys nothing — it is not a JWT, and
        the internal stack never learns to read it."""
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        for url in ("/api/quotations", f"/api/quotations/{quotation.id}", "/api/approvals"):
            self.assertEqual(client.get(url).status_code, 401, url)

    def test_expired_and_revoked_links_stop_working(self):
        quotation = self.make_quotation()
        session, token = issue_session(quotation, self.rep)

        session.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        session.save(update_fields=["expires_at"])
        self.assertEqual(
            self.portal_client().get(f"/api/portal/quotations/{token}").status_code, 401
        )

        session.expires_at = timezone.now() + timezone.timedelta(hours=1)
        session.revoked_at = timezone.now()
        session.save(update_fields=["expires_at", "revoked_at"])
        with self.assertRaises(PortalAccessDenied):
            resolve_token(token)

    def test_issuing_a_replacement_revokes_the_previous_link(self):
        quotation = self.make_quotation()
        _, first = issue_session(quotation, self.rep)
        _, second = issue_session(quotation, self.rep)

        client = self.portal_client()
        self.assertEqual(client.get(f"/api/portal/quotations/{first}").status_code, 401)
        self.assertEqual(client.get(f"/api/portal/quotations/{second}").status_code, 200)

    def test_raw_token_is_never_stored(self):
        quotation = self.make_quotation()
        session, token = issue_session(quotation, self.rep)
        session.refresh_from_db()
        self.assertNotIn(token, session.token_hash)
        self.assertEqual(len(session.token_hash), 64)

    def test_draft_quotations_cannot_be_shared(self):
        quotation = self.make_quotation(status=Quotation.DRAFT)
        with self.assertRaises(ValueError):
            issue_session(quotation, self.rep)


class CounterOfferRoutingTests(PortalTestBase):
    """§7.1 / §11: the customer's counter-offer runs the same engine a rep edit does."""

    def counter(self, token, pct, **extra):
        return self.portal_client().post(
            f"/api/portal/{token}/counter-offer",
            {"counter_discount_pct": pct, **extra},
            format="json",
        )

    def test_within_threshold_counter_offer_needs_no_approval(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        # 10% clears Hardware (15%) and sits exactly on the Services ceiling (10%).
        response = self.counter(token, "10")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["sent_for_approval"])

        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.APPROVED)
        self.assertFalse(
            quotation.approval_requests.filter(status=ApprovalRequest.PENDING).exists()
        )
        self.assertTrue(all(l.discount_pct == D("10.00") for l in quotation.lines.all()))

    def test_over_threshold_counter_offer_reopens_approval(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        # 30%: Hardware is 15 over, Services 20 over -> routing score 20 -> both stages.
        response = self.counter(token, "30", body="We need 30%.")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["sent_for_approval"])

        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.PENDING_APPROVAL)

        request = quotation.approval_requests.get(status=ApprovalRequest.PENDING)
        self.assertEqual(request.risk_score_snapshot, D("20.00"))
        self.assertEqual(request.required_level, "manager_then_finance")
        self.assertEqual(
            list(request.steps.order_by("sequence").values_list("stage", flat=True)),
            [ApprovalStep.MANAGER, ApprovalStep.FINANCE],
        )
        self.assertTrue(all(s.action == ApprovalStep.PENDING for s in request.steps.all()))

    def test_second_negotiation_round_opens_a_brand_new_cycle(self):
        """§5.5: each round gets its own request and its own snapshot. Reusing the first
        would leave reviewers signing off a score the quote no longer has."""
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        # Round one: 12% is 2 points over the Services ceiling -> Sales Manager only.
        self.counter(token, "12")
        # Fetched through the manager, not `quotation.approval_requests`: the reverse
        # accessor would hand `act_on_request` this test's own stale Quotation instance.
        first = ApprovalRequest.objects.get(
            quotation=quotation, status=ApprovalRequest.PENDING
        )
        self.assertEqual(first.risk_score_snapshot, D("2.00"))
        self.assertEqual(first.required_level, "manager")

        act_on_request(
            first,
            self.manager,
            Membership.objects.get(user=self.manager, company=self.company),
            ApprovalStep.APPROVED,
        )
        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.APPROVED)

        # Round two: the customer pushes further, and that must not touch round one.
        self.counter(token, "30")
        quotation.refresh_from_db()

        first.refresh_from_db()
        self.assertEqual(first.status, ApprovalRequest.APPROVED)
        second = ApprovalRequest.objects.get(
            quotation=quotation, status=ApprovalRequest.PENDING
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(second.risk_score_snapshot, D("20.00"))
        self.assertEqual(second.required_level, "manager_then_finance")
        # A fresh chain, with nobody's earlier sign-off carried over into it.
        self.assertTrue(all(s.action == ApprovalStep.PENDING for s in second.steps.all()))

    def test_line_scoped_counter_offer_only_moves_that_line(self):
        quotation = self.make_quotation()
        laptop_line = quotation.lines.get(product=self.laptop)
        warranty_line = quotation.lines.get(product=self.warranty)
        _, token = issue_session(quotation, self.rep)

        # 14% is fine on Hardware (ceiling 15) but would be 4 over on Services — proof the
        # ceiling is read per category, not per quote.
        response = self.counter(token, "14", quotation_line=str(laptop_line.id))
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["sent_for_approval"])

        laptop_line.refresh_from_db()
        warranty_line.refresh_from_db()
        self.assertEqual(laptop_line.discount_pct, D("14.00"))
        self.assertEqual(warranty_line.discount_pct, D("5.00"))

    def test_counter_offer_is_audited_as_a_customer_action(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)
        self.counter(token, "30")

        entry = AuditEntry.objects.get(object_id=quotation.id, action="portal_counter_offer")
        # No internal user: nobody on staff did this, and the trail must not imply one did.
        self.assertIsNone(entry.user_id)
        self.assertEqual(entry.metadata["triggered_by"], "customer_counter_offer")
        self.assertEqual(entry.metadata["counter_discount_pct"], "30.00")

        routed = AuditEntry.objects.filter(
            object_id=quotation.id, action="approval_requested"
        ).first()
        self.assertEqual(routed.metadata["trigger"], "portal_counter_offer")

    def test_counter_offer_writes_a_thread_message_the_rep_can_read(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)
        self.counter(token, "30", body="Best you can do?")

        message = NegotiationMessage.objects.get(
            quotation=quotation, message_type=NegotiationMessage.COUNTER_OFFER
        )
        self.assertEqual(message.counter_discount_pct, D("30.00"))
        self.assertEqual(message.author_customer_id, self.customer.id)
        self.assertIsNone(message.author_user_id)
        self.assertTrue(
            NegotiationMessage.objects.filter(
                quotation=quotation, message_type=NegotiationMessage.SYSTEM
            ).exists()
        )


class ConfirmationTests(PortalTestBase):
    def test_confirm_within_policy_wins_the_deal(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        response = self.portal_client().post(
            f"/api/portal/{token}/confirm", {"body": "We accept."}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["confirmed"])

        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.CONFIRMED)
        self.assertTrue(
            NegotiationMessage.objects.filter(
                quotation=quotation, message_type=NegotiationMessage.CONFIRMATION
            ).exists()
        )

    def test_confirm_rechecks_terms_and_refuses_when_they_breach_policy(self):
        """The window this closes: terms changed after the last routing (a rep edit while
        the customer had the tab open). Trusting `status == approved` would turn an
        unapproved discount into a won deal."""
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)

        line = quotation.lines.get(product=self.warranty)
        line.discount_pct = D("40.00")
        line.save()

        response = self.portal_client().post(
            f"/api/portal/{token}/confirm", {}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["confirmed"])
        self.assertTrue(response.json()["sent_for_approval"])

        quotation.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.PENDING_APPROVAL)
        self.assertTrue(
            quotation.approval_requests.filter(status=ApprovalRequest.PENDING).exists()
        )

    def test_customer_cannot_act_while_the_quote_is_under_review(self):
        quotation = self.make_quotation(status=Quotation.PENDING_APPROVAL)
        _, token = issue_session(quotation, self.rep)
        client = self.portal_client()

        # Readable — the customer can still see where their deal stands...
        self.assertEqual(client.get(f"/api/portal/quotations/{token}").status_code, 200)
        # ...but not movable while it sits with the internal reviewers.
        self.assertEqual(
            client.post(f"/api/portal/{token}/confirm", {}, format="json").status_code, 409
        )
        self.assertEqual(
            client.post(
                f"/api/portal/{token}/counter-offer",
                {"counter_discount_pct": "5"},
                format="json",
            ).status_code,
            409,
        )


class InternalSideTests(PortalTestBase):
    """The thread is one conversation reached through two auth boundaries (§5.9)."""

    def internal(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_rep_can_generate_a_portal_link(self):
        quotation = self.make_quotation()
        response = self.internal(self.rep).post(
            f"/api/quotations/{quotation.id}/generate-portal-link", {}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("/portal/quotations/", body["portal_url"])
        self.assertTrue(PortalSession.objects.filter(quotation=quotation).exists())

        # The minted token really works, end to end.
        self.assertEqual(
            self.portal_client()
            .get(f"/api/portal/quotations/{body['token']}")
            .status_code,
            200,
        )

    def test_generating_a_link_emails_the_customer(self):
        """Spec A1: the link must actually reach the customer's inbox, not just sit on
        the rep's screen to copy by hand. Django's test runner swaps in the locmem email
        backend regardless of settings, so a real send is captured in `mail.outbox`."""
        from django.core import mail

        quotation = self.make_quotation()
        response = self.internal(self.rep).post(
            f"/api/quotations/{quotation.id}/generate-portal-link", {}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["emailed"])

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, [self.customer.email])
        self.assertIn(quotation.number, sent.subject)
        self.assertIn(response.json()["portal_url"], sent.body)

    def test_a_broken_email_backend_does_not_break_the_link_response(self):
        """The rep must still get the link even if outbound email is misconfigured —
        see `portal.services.send_portal_link_email`'s broad except."""
        from unittest.mock import patch

        quotation = self.make_quotation()
        with patch("portal.services.send_mail", side_effect=RuntimeError("smtp down")):
            response = self.internal(self.rep).post(
                f"/api/quotations/{quotation.id}/generate-portal-link", {}, format="json"
            )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["emailed"])
        self.assertIn("/portal/quotations/", response.json()["portal_url"])

    def test_rep_cannot_generate_a_link_for_someone_elses_deal(self):
        other_rep = User.objects.create_user(email="rep2@test.com", password="x")
        Membership.objects.create(
            user=other_rep,
            company=self.company,
            role=Role.objects.get(code=Role.SALES_REP),
            is_active_default=True,
        )
        quotation = self.make_quotation()

        response = self.internal(other_rep).post(
            f"/api/quotations/{quotation.id}/generate-portal-link", {}, format="json"
        )
        # Owner scoping happens in the queryset, so the quote is simply not there.
        self.assertIn(response.status_code, (403, 404))

    def test_generate_link_requires_authentication(self):
        quotation = self.make_quotation()
        response = APIClient().post(
            f"/api/quotations/{quotation.id}/generate-portal-link", {}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_internal_thread_shows_customer_messages_and_accepts_replies(self):
        quotation = self.make_quotation()
        _, token = issue_session(quotation, self.rep)
        self.portal_client().post(
            f"/api/portal/{token}/comment", {"body": "Any movement on price?"}, format="json"
        )

        client = self.internal(self.manager)
        thread = client.get(f"/api/quotations/{quotation.id}/negotiation").json()
        self.assertEqual(len(thread), 1)
        self.assertEqual(thread[0]["author_side"], "customer")

        reply = client.post(
            f"/api/quotations/{quotation.id}/negotiation",
            {"body": "Let me check with finance."},
            format="json",
        )
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(reply.json()["author_side"], "internal")

        # And the customer sees that reply through their own boundary.
        portal = self.portal_client().get(f"/api/portal/quotations/{token}").json()
        sides = [m["author_side"] for m in portal["quotation"]["messages"]]
        self.assertEqual(sides, ["customer", "internal"])

    def test_quotation_detail_carries_the_thread_and_link_state(self):
        quotation = self.make_quotation()
        issue_session(quotation, self.rep)
        detail = self.internal(self.rep).get(f"/api/quotations/{quotation.id}").json()
        self.assertIn("negotiation", detail)
        self.assertIsNotNone(detail["portal_link"])
        # Never the credential itself, only its lifecycle.
        self.assertNotIn("token", detail["portal_link"])


class CustomerLoginTests(PortalTestBase):
    """Email+password login (spec A1) — the customer's second entry point, alongside a
    rep-sent magic link, and the "My Quotations" list it unlocks."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer.set_password("hunter2pass")
        cls.customer.save(update_fields=["password_hash"])

    def test_login_with_correct_password_succeeds(self):
        response = self.portal_client().post(
            "/api/portal/login", {"email": "buy@test.com", "password": "hunter2pass"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("customer_token", response.json())
        self.assertEqual(response.json()["customer"]["email"], "buy@test.com")

    def test_login_with_wrong_password_is_rejected(self):
        response = self.portal_client().post(
            "/api/portal/login", {"email": "buy@test.com", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_login_for_customer_with_no_password_set_is_rejected(self):
        response = self.portal_client().post(
            "/api/portal/login",
            {"email": self.other_customer.email, "password": "anything"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def _login_token(self):
        response = self.portal_client().post(
            "/api/portal/login", {"email": "buy@test.com", "password": "hunter2pass"}, format="json"
        )
        return response.json()["customer_token"]

    def test_my_quotations_lists_only_this_customers_shareable_quotes(self):
        mine_approved = self.make_quotation(status=Quotation.APPROVED)
        mine_draft = self.make_quotation(status=Quotation.DRAFT)
        someone_elses = self.make_quotation(customer=self.other_customer, status=Quotation.APPROVED)

        token = self._login_token()
        response = self.portal_client().get(f"/api/portal/me/quotations/{token}")
        self.assertEqual(response.status_code, 200)
        numbers = {q["number"] for q in response.json()["quotations"]}

        self.assertIn(mine_approved.number, numbers)
        self.assertNotIn(mine_draft.number, numbers)  # not submitted yet — not theirs to see
        self.assertNotIn(someone_elses.number, numbers)  # a different customer entirely

    def test_open_quotation_mints_a_working_single_quotation_session(self):
        quotation = self.make_quotation(status=Quotation.APPROVED)
        token = self._login_token()

        response = self.portal_client().post(
            f"/api/portal/me/quotations/{token}/{quotation.id}/open"
        )
        self.assertEqual(response.status_code, 201)
        quotation_token = response.json()["token"]

        # The minted token opens the exact same detail screen a magic link would.
        detail = self.portal_client().get(f"/api/portal/quotations/{quotation_token}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["quotation"]["number"], quotation.number)

    def test_cannot_open_a_quotation_belonging_to_someone_else(self):
        someone_elses = self.make_quotation(customer=self.other_customer, status=Quotation.APPROVED)
        token = self._login_token()

        response = self.portal_client().post(
            f"/api/portal/me/quotations/{token}/{someone_elses.id}/open"
        )
        self.assertEqual(response.status_code, 403)

    def test_garbage_customer_token_is_rejected(self):
        response = self.portal_client().get("/api/portal/me/quotations/not-a-real-token")
        self.assertEqual(response.status_code, 401)
