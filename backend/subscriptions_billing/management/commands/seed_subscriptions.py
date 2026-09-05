"""Seeds the subscriptions / billing slice of spec §13.

Three deliberately different situations, so every branch of §7.3 can be exercised without
hand-editing rows:

  A. A **mixed order** confirmed today — one one-time hardware line and one recurring
     service line on the same quotation. It raises a single invoice carrying both, in two
     structurally separate line pools. This is the case the split billing view exists for.
  B. A **mid-cycle subscription**, also from a mixed order, backdated ~45 days into a
     quarterly period so a quantity change has real days left to prorate against.
  C. A **migrated contract** with no originating quotation, whose current period was
     billed outside DealFlow360. Cancelling it produces a credit note that attaches
     directly to the subscription, because no invoice of ours is involved (§5.10).

Idempotent: re-running matches on the existing quotation / subscription and leaves it be.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Company, Customer, User
from catalog.models import Product
from quotations.models import Quotation, QuotationLine
from subscriptions_billing.models import Subscription, SubscriptionPlan
from subscriptions_billing.services import create_subscription

COMPANY_NAME = "Acme Solutions"

# name, product, cycle, proration mode, cancellation rule
PLANS = [
    (
        "Care Plan 2yr",
        "Onsite Support Plan",
        SubscriptionPlan.QUARTERLY,
        {"mode": "daily"},
        {"type": SubscriptionPlan.PRORATED_REFUND},
    ),
    (
        "M365 Annual Licence",
        "Microsoft 365 Business",
        SubscriptionPlan.YEARLY,
        {"mode": "daily"},
        {"type": SubscriptionPlan.NO_REFUND},
    ),
    (
        # Not bound to a product: the fallback any other recurring line resolves to, and
        # the one plan carrying a full_refund rule so that branch is reachable too.
        "Standard Monthly Care",
        None,
        SubscriptionPlan.MONTHLY,
        {"mode": "daily"},
        {"type": SubscriptionPlan.FULL_REFUND},
    ),
]

# owner email, customer, [(product, qty, discount_pct, line_type)], backdate days, note
ORDERS = [
    (
        "rohan@company.com",
        "TechCorp Solutions",
        [
            ("Dell Latitude 5440", 5, "0.00", QuotationLine.ONE_TIME),
            ("Onsite Support Plan", 10, "0.00", QuotationLine.RECURRING),
        ],
        0,
        "Mixed order billed today: hardware + a quarterly service subscription.",
    ),
    (
        "karan@company.com",
        "Global Retail Ltd",
        [
            ("Training & Onboarding", 2, "0.00", QuotationLine.ONE_TIME),
            ("Onsite Support Plan", 8, "0.00", QuotationLine.RECURRING),
        ],
        45,
        "Mixed order backdated 45 days: sits mid-cycle, ready for a proration test.",
    ),
    (
        "rohan@company.com",
        "Acme Technologies Pvt Ltd",
        [
            ("Extended Warranty", 3, "0.00", QuotationLine.ONE_TIME),
            ("Microsoft 365 Business", 20, "0.00", QuotationLine.RECURRING),
        ],
        60,
        "Mixed order on a no_refund yearly plan: cancelling it credits nothing even "
        "though most of the year is unserved — proof the rule drives the outcome.",
    ),
]

MIGRATED = {
    "customer": "Acme Technologies Pvt Ltd",
    "product": "Onsite Support Plan",
    "qty": Decimal("6"),
    "backdate_days": 40,
}


def backdate(subscription, days):
    """Shift a whole subscription — its periods, its order invoice — back in time so it
    sits mid-cycle. Every date moves by the same delta, so the schedule stays coherent and
    the (subscription, period_start) uniqueness still holds."""
    shift = timedelta(days=days)
    subscription.start_date -= shift
    subscription.next_bill_date -= shift
    subscription.save(update_fields=["start_date", "next_bill_date", "updated_at"])

    invoices = set()
    for cycle in subscription.billing_cycles.all():
        cycle.period_start -= shift
        cycle.period_end -= shift
        cycle.save(update_fields=["period_start", "period_end", "updated_at"])
        if cycle.invoice_line_id:
            invoices.add(cycle.invoice_line.invoice)

    for invoice in invoices:
        invoice.issue_date -= shift
        if invoice.due_date:
            invoice.due_date -= shift
        invoice.save(update_fields=["issue_date", "due_date", "updated_at"])


class Command(BaseCommand):
    help = "Seed subscription plans plus mixed one-time/recurring orders and their billing."

    # Deliberately not wrapped in one atomic block: confirming a quotation provisions
    # billing through a `transaction.on_commit` hook, and the backdating below has to run
    # against subscriptions that already exist.
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first.")
        if not Product.objects.filter(company=company).exists():
            raise SystemExit("No products found. Run `seed_catalog` first.")

        self.seed_plans(company)
        self.seed_orders(company)
        self.seed_migrated(company)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {SubscriptionPlan.objects.filter(company=company).count()} plan(s), "
                f"{Subscription.objects.filter(customer__company=company).count()} subscription(s)."
            )
        )

    # -- plans ------------------------------------------------------------------

    def seed_plans(self, company):
        for name, product_name, cycle, proration, cancellation in PLANS:
            product = (
                Product.objects.filter(company=company, name=product_name).first()
                if product_name
                else None
            )
            plan, created = SubscriptionPlan.objects.get_or_create(
                company=company,
                name=name,
                defaults={
                    "product": product,
                    "cycle": cycle,
                    "proration_rule": proration,
                    "cancellation_rule": cancellation,
                },
            )
            self.stdout.write(
                f"{'created' if created else 'reused '}  plan          {plan.name:<24} "
                f"{plan.cycle:<10} {plan.refund_type}"
            )

    # -- mixed orders -----------------------------------------------------------

    def seed_orders(self, company):
        for owner_email, customer_name, lines, backdate_days, note in ORDERS:
            owner = User.objects.get(email=owner_email)
            customer = Customer.objects.get(company=company, name=customer_name)

            # Keyed on a quotation for this pair that already carries *both* line types.
            # Matching on owner+customer alone would collide with quotations the other
            # seeds (or a tester) happened to create for the same pair.
            existing = next(
                (
                    quotation
                    for quotation in Quotation.objects.filter(
                        company=company, owner=owner, customer=customer
                    ).prefetch_related("lines")
                    if {line.line_type for line in quotation.lines.all()}
                    == {QuotationLine.ONE_TIME, QuotationLine.RECURRING}
                ),
                None,
            )
            if existing:
                self.stdout.write(
                    f"reused   quotation     {existing.number} ({existing.status}) — mixed order"
                )
                continue

            quotation = Quotation.objects.create(
                company=company, customer=customer, owner=owner
            )
            for product_name, qty, discount, line_type in lines:
                product = Product.objects.get(company=company, name=product_name)
                QuotationLine.objects.create(
                    quotation=quotation,
                    product=product,
                    qty=Decimal(qty),
                    unit_price=product.base_price,
                    discount_pct=Decimal(discount),
                    line_type=line_type,
                )

            # Straight to confirmed: these are won deals, and every line is inside policy
            # so there is nothing for the approval chain to weigh in on. The status change
            # is what triggers provisioning (§11).
            quotation.set_status(Quotation.CONFIRMED, owner)
            quotation.refresh_from_db()

            invoice = quotation.invoices.first()
            self.stdout.write(
                f"created  quotation     {quotation.number}  {customer.name} — "
                f"invoice {invoice.invoice_number if invoice else '(none)'} "
                f"({len(invoice.one_time_lines) if invoice else 0} one-time / "
                f"{len(invoice.recurring_lines) if invoice else 0} recurring lines)"
            )
            self.stdout.write(f"         {note}")

            if backdate_days:
                for subscription in quotation.subscriptions.all():
                    backdate(subscription, backdate_days)
                    subscription.refresh_from_db()
                    cycle = subscription.current_cycle
                    self.stdout.write(
                        f"         backdated {backdate_days}d — current period "
                        f"{cycle.period_start} to {cycle.period_end}, "
                        f"{cycle.days_remaining(timezone.localdate())} of "
                        f"{cycle.days_in_cycle} days left"
                    )

    # -- migrated contract ------------------------------------------------------

    def seed_migrated(self, company):
        customer = Customer.objects.get(company=company, name=MIGRATED["customer"])
        product = Product.objects.get(company=company, name=MIGRATED["product"])
        plan = SubscriptionPlan.objects.get(company=company, name="Care Plan 2yr")

        if Subscription.objects.filter(
            customer=customer, product=product, quotation__isnull=True
        ).exists():
            self.stdout.write("reused   subscription  migrated contract already seeded")
            return

        start = timezone.localdate() - timedelta(days=MIGRATED["backdate_days"])
        subscription = create_subscription(
            quotation=None,
            plan=plan,
            product=product,
            customer=customer,
            qty=MIGRATED["qty"],
            unit_price=product.base_price,
            start_date=start,
        )
        # The current period was charged by the previous provider before the contract
        # moved across: settled, so it must not bill again, but there is no invoice of
        # ours behind it.
        first_cycle = subscription.billing_cycles.first()
        first_cycle.billed_externally = True
        first_cycle.save(update_fields=["billed_externally", "updated_at"])

        self.stdout.write(
            f"created  subscription  migrated {product.name} x{subscription.qty} for "
            f"{customer.name} — current period billed externally, no invoice behind it"
        )
        self.stdout.write(
            "         Cancel this one to see a credit note attach directly to the "
            "subscription (§5.10)."
        )
