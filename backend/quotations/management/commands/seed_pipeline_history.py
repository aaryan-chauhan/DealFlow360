"""Seeds a richer, realistic deal pipeline on top of `seed_quotations`: more reps, more
customers, more products, spread across the last five weeks with every terminal outcome
represented (auto-approved, open pending at both approval levels, resolved by a manager,
resolved by manager+finance, rejected, returned-to-draft, confirmed with billing, and a
quote stale enough to trip the Deal Health "stalled deal" scan).

Must run after `seed_fulfillment` and `seed_subscriptions` (so warehouses/stock and
subscription plans already exist before any of these quotations flip to approved/confirmed
and fire those apps' signals) and before `seed_portal`/`seed_deal_health`. Idempotent: keyed
on (owner, customer, first product), so re-running finds the same quotes rather than piling
up duplicates.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Company, Customer, Membership, Role, User
from approvals.models import ApprovalStep
from approvals.services import act_on_request, open_request_for, route_quotation
from catalog.models import Product
from quotations.models import Quotation, QuotationLine

COMPANY_NAME = "Acme Solutions"

AUTO_APPROVE = "auto_approve"
OPEN_PENDING = "open_pending"
APPROVED_BY_MANAGER = "approved_by_manager"
APPROVED_BY_MANAGER_AND_FINANCE = "approved_by_manager_and_finance"
REJECTED = "rejected"
RETURNED = "returned"
STALE_DRAFT = "stale_draft"

# owner, customer, [(product, qty, discount_pct)], age_days, outcome, then_confirm, reason
DEALS = [
    (
        "meera@company.com", "Bluewave Industries",
        [("HP EliteBook 840", 3, "12.00")],
        2, AUTO_APPROVE, False, "",
        "Gold + Hardware ceiling 15% -> 12% clears it outright.",
    ),
    (
        "vikram@company.com", "Horizon Retail Group",
        [("Cloud Backup Service", 15, "18.00")],
        6, OPEN_PENDING, False, "",
        "Silver + Software ceiling 10% -> 8 pts over, routes to Sales Manager. Left open for you to approve.",
    ),
    (
        "meera@company.com", "Horizon Retail Group",
        [("Dell Latitude 5440", 8, "30.00")],
        10, OPEN_PENDING, False, "",
        "Silver + Hardware ceiling 10% -> 20 pts over, routes to Manager then Finance. Left open for you to approve.",
    ),
    (
        "vikram@company.com", "Nimbus Startups Pvt Ltd",
        [("Training & Onboarding", 1, "5.00")],
        1, AUTO_APPROVE, False, "",
        "Bronze + Services ceiling 5% -> exactly at cap, auto-approved.",
    ),
    (
        "rohan@company.com", "Bluewave Industries",
        [("HP EliteBook 840", 2, "22.00")],
        20, APPROVED_BY_MANAGER, False, "",
        "Gold + Hardware ceiling 15% -> 7 pts over, Sales Manager already signed off.",
    ),
    (
        "karan@company.com", "Nimbus Startups Pvt Ltd",
        [("Extended Warranty", 5, "30.00")],
        35, APPROVED_BY_MANAGER_AND_FINANCE, True, "",
        "Bronze + Services ceiling 5% -> 25 pts over, Manager + Finance both signed off, then won.",
    ),
    (
        "meera@company.com", "Nimbus Startups Pvt Ltd",
        [("Onsite Support Plan", 4, "40.00")],
        15, REJECTED, False,
        "Discount far exceeds policy ceiling; renegotiate closer to the 5% cap and resubmit.",
        "Bronze + Services ceiling 5% -> 35 pts over, Sales Manager rejected it.",
    ),
    (
        "vikram@company.com", "Bluewave Industries",
        [("Microsoft 365 Business", 10, "25.00")],
        8, RETURNED, False,
        "25% is well outside the 10% software ceiling for a Gold account — re-quote at 15% or below and resubmit.",
        "Gold + Software ceiling 10% -> 15 pts over, Sales Manager returned it to draft.",
    ),
    (
        "rohan@company.com", "Horizon Retail Group",
        [("Dell Latitude 5440", 1, "0.00")],
        25, STALE_DRAFT, False, "",
        "Never submitted, untouched for 25 days -> Deal Health should flag this as stalled.",
    ),
    (
        "karan@company.com", "Bluewave Industries",
        [("Cloud Backup Service", 5, "8.00")],
        0, AUTO_APPROVE, True, "",
        "Gold + Software ceiling 10% -> clears it, auto-approved and won today (adds a subscription).",
    ),
]


class Command(BaseCommand):
    help = "Seed a realistic, varied deal pipeline: more reps/customers/products, full approval history."

    def find_existing(self, company, owner, customer, first_product_name):
        return (
            Quotation.objects.filter(company=company, owner=owner, customer=customer)
            .filter(lines__product__name=first_product_name)
            .first()
        )

    def backdate(self, quotation, age_days, also_stale):
        when = timezone.now() - timedelta(days=age_days)
        fields = {"created_at": when}
        if also_stale:
            fields["updated_at"] = when
        Quotation.objects.filter(pk=quotation.pk).update(**fields)

    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first.")

        manager = Membership.objects.get(
            company=company, role__code=Role.SALES_MANAGER
        )
        finance = Membership.objects.get(
            company=company, role__code=Role.FINANCE_OPS
        )

        for owner_email, customer_name, lines, age_days, outcome, then_confirm, reason, note in DEALS:
            owner = User.objects.get(email=owner_email)
            customer = Customer.objects.get(company=company, name=customer_name)
            first_product = lines[0][0]

            existing = self.find_existing(company, owner, customer, first_product)
            if existing:
                self.stdout.write(f"reused   {existing.number}  ({existing.status})  {note}")
                continue

            quotation = Quotation.objects.create(company=company, customer=customer, owner=owner)
            for product_name, qty, discount in lines:
                product = Product.objects.get(company=company, name=product_name)
                QuotationLine.objects.create(
                    quotation=quotation,
                    product=product,
                    qty=Decimal(qty),
                    unit_price=product.base_price,
                    discount_pct=Decimal(discount),
                    line_type=(
                        QuotationLine.RECURRING if product.is_subscription else QuotationLine.ONE_TIME
                    ),
                )

            also_stale = outcome in (OPEN_PENDING, STALE_DRAFT)

            if outcome == STALE_DRAFT:
                self.backdate(quotation, age_days, also_stale)
                self.stdout.write(f"created  {quotation.number}  {owner.full_name} / {customer.name}  draft (stale)")
                self.stdout.write(f"         {note}")
                continue

            assessment, request = route_quotation(quotation, owner)
            quotation.refresh_from_db()

            if outcome == AUTO_APPROVE:
                if then_confirm:
                    quotation.set_status(Quotation.CONFIRMED, owner)
                self.backdate(quotation, age_days, also_stale)
                self.stdout.write(
                    f"created  {quotation.number}  {owner.full_name} / {customer.name}  "
                    f"score {assessment.routing_score} -> {quotation.status}"
                )
                self.stdout.write(f"         {note}")
                continue

            if outcome == OPEN_PENDING:
                self.backdate(quotation, age_days, also_stale)
                self.stdout.write(
                    f"created  {quotation.number}  {owner.full_name} / {customer.name}  "
                    f"score {assessment.routing_score} -> pending_approval (left open)"
                )
                self.stdout.write(f"         {note}")
                continue

            # Everything below has a real ApprovalRequest to act on.
            open_request = open_request_for(quotation)
            if outcome in (APPROVED_BY_MANAGER, APPROVED_BY_MANAGER_AND_FINANCE):
                act_on_request(
                    open_request, manager.user, manager, ApprovalStep.APPROVED,
                    reason="Within acceptable range for this account.",
                )
                if outcome == APPROVED_BY_MANAGER_AND_FINANCE:
                    open_request.refresh_from_db()
                    act_on_request(
                        open_request, finance.user, finance, ApprovalStep.APPROVED,
                        reason="Margin still acceptable at this volume; approved.",
                    )
                quotation.refresh_from_db()
                if then_confirm:
                    quotation.set_status(Quotation.CONFIRMED, owner)
            elif outcome == REJECTED:
                act_on_request(open_request, manager.user, manager, ApprovalStep.REJECTED, reason=reason)
            elif outcome == RETURNED:
                act_on_request(open_request, manager.user, manager, ApprovalStep.RETURNED, reason=reason)

            quotation.refresh_from_db()
            self.backdate(quotation, age_days, also_stale)
            self.stdout.write(
                f"created  {quotation.number}  {owner.full_name} / {customer.name}  "
                f"score {assessment.routing_score} -> {quotation.status}"
            )
            self.stdout.write(f"         {note}")

        self.stdout.write(self.style.SUCCESS("\nDone. Pipeline history seeded."))
