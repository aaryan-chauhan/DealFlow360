"""Recurring revenue (spec §5.8).

`cycle` lives on the plan rather than the subscription because the cycle length is part
of the template an admin configures (Screen A5) and is reused across every customer on
that plan.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Company, Customer, TimeStampedModel, UUIDModel
from catalog.models import Product
from quotations.models import Quotation

ZERO = Decimal("0.00")


def add_months(day, months):
    """Advance a date by whole months, clamping to the last valid day of the target
    month. Hand-written rather than pulled from `dateutil` to keep the dependency list
    as it is; the clamp is what stops a 31 Jan subscription from throwing on 28 Feb."""
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    if month == 12:
        next_month_start = day.replace(year=year + 1, month=1, day=1)
    else:
        next_month_start = day.replace(year=year, month=month + 1, day=1)
    last_day = (next_month_start - timedelta(days=1)).day
    return day.replace(year=year, month=month, day=min(day.day, last_day))


class SubscriptionPlan(UUIDModel, TimeStampedModel):
    """The admin-configured template (Screen A5), reused across many customers."""

    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"
    CYCLE_CHOICES = [(MONTHLY, MONTHLY), (QUARTERLY, QUARTERLY), (YEARLY, YEARLY)]
    CYCLE_MONTHS = {MONTHLY: 1, QUARTERLY: 3, YEARLY: 12}

    FULL_REFUND = "full_refund"
    PRORATED_REFUND = "prorated_refund"
    NO_REFUND = "no_refund"
    REFUND_TYPES = (FULL_REFUND, PRORATED_REFUND, NO_REFUND)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="subscription_plans"
    )
    # §13 seeds a plan "attached to a serviceable product", and provisioning has to know
    # which plan a recurring quotation line becomes. Nullable so a generic plan can exist
    # without being bound to one SKU.
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_plans",
    )
    name = models.CharField(max_length=255)
    cycle = models.CharField(max_length=16, choices=CYCLE_CHOICES, default=MONTHLY)
    # {"mode": "daily" | "none"} — how a mid-cycle change is valued (§7.3.2).
    proration_rule = models.JSONField(default=dict, blank=True)
    # {"type": "full_refund" | "prorated_refund" | "no_refund"} (§7.3.3).
    cancellation_rule = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_plan_company_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.cycle})"

    @property
    def cycle_months(self):
        return self.CYCLE_MONTHS[self.cycle]

    @property
    def refund_type(self):
        """Defaults to no_refund: a plan whose rule was never configured must not
        silently hand money back."""
        value = (self.cancellation_rule or {}).get("type", self.NO_REFUND)
        return value if value in self.REFUND_TYPES else self.NO_REFUND

    @property
    def prorates(self):
        return (self.proration_rule or {}).get("mode", "daily") != "none"

    def period_end_from(self, start):
        return add_months(start, self.cycle_months)


class Subscription(UUIDModel, TimeStampedModel):
    """A live recurring commitment.

    `quotation` is SET NULL because a subscription must *outlive* the quotation it came
    from — the quote can be archived years later, billing history cannot disappear with
    it (§5.8). `customer` is PROTECT, so `customer.company` stays a reliable tenant
    anchor even once the quotation link has been cleared.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (PAUSED, "Paused"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    ]

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="subscriptions")
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="subscriptions"
    )
    qty = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    # Snapshot of the per-cycle unit price at provisioning time, carried across from the
    # quotation line. Not a live join to `price_list_item`, for the same reason a
    # quotation line snapshots its price (§5.4): a list-price change must never silently
    # re-price a contract that is already running.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    start_date = models.DateField()
    next_bill_date = models.DateField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    # Set while paused, cleared on resume. Used to shift the billing clock forward by
    # however long the pause lasted, so a customer is never billed for time on hold.
    paused_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscription"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} x{self.qty} for {self.customer.name}"

    @property
    def company(self):
        """Tenant anchor. Read off the customer, not the quotation, because the
        quotation link is nullable by design."""
        return self.customer.company

    @property
    def cycle_amount(self):
        """The standard, un-prorated charge for one period."""
        return (self.qty * self.unit_price).quantize(Decimal("0.01"))

    @property
    def current_cycle(self):
        """The period covering today, else the earliest not-yet-billed one. This is what
        the screens headline as "current period" and what proration is measured against."""
        today = timezone.localdate()
        cycles = list(self.billing_cycles.all())
        for cycle in cycles:
            if cycle.period_start <= today < cycle.period_end:
                return cycle
        return next((cycle for cycle in cycles if not cycle.is_billed), None)


class BillingCycle(UUIDModel, TimeStampedModel):
    """One row per billing period.

    Exists *before* the invoice line does — it is the scheduled/upcoming charge the
    billing schedule renders (Screen 10), later realised into a real invoice line when
    the cycle bills (§5.8). Whether a period is settled is derived from `invoice_line`
    (plus `billed_externally` for migrated contracts) rather than stored in a status
    column of its own, so it can never drift out of sync with the invoice that was
    actually raised.
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="billing_cycles"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    invoice_line = models.OneToOneField(
        "invoicing_payments.InvoiceLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_cycle",
    )
    # A contract migrated in mid-term: this period was charged outside DealFlow360, so it
    # is settled and must not bill again, but there is no `invoice_line` to point at.
    # This is the case §5.10 has in mind when a credit note attaches directly to the
    # subscription rather than to an invoice.
    billed_externally = models.BooleanField(default=False)

    class Meta:
        db_table = "billing_cycle"
        ordering = ["period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "period_start"], name="uniq_cycle_subscription_period"
            )
        ]

    def __str__(self):
        return f"{self.period_start} -> {self.period_end}: {self.amount}"

    @property
    def is_billed(self):
        """Settled one way or the other — through an invoice we raised, or outside the
        system for a migrated contract. Either way it must never bill again."""
        return self.invoice_line_id is not None or self.billed_externally

    @property
    def days_in_cycle(self):
        """Actual days in this period, not a nominal 30 — §7.3.2 divides by it, and a
        quarterly cycle spanning February really is shorter than one spanning summer."""
        return max(1, (self.period_end - self.period_start).days)

    def days_remaining(self, as_of):
        """Days left to serve, clamped to [0, days_in_cycle] so a change dated outside the
        period can never produce a negative or an inflated proration."""
        return max(0, min(self.days_in_cycle, (self.period_end - as_of).days))


class ProrationEvent(UUIDModel):
    """Logs a mid-cycle change and its prorated adjustment — the audit trail for "why did
    this month's invoice differ from the standard amount" (§5.8).

    `billing_cycle` records which period actually absorbed the delta. §7.3.2 lets the
    adjustment land on the current *or* the next cycle, so without this link the number
    on the invoice could not be traced back to the change that produced it.
    """

    QTY_CHANGE = "qty_change"
    PLAN_CHANGE = "plan_change"
    CANCELLATION = "cancellation"
    CHANGE_CHOICES = [
        (QTY_CHANGE, "Quantity change"),
        (PLAN_CHANGE, "Plan change"),
        (CANCELLATION, "Cancellation"),
    ]

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="proration_events"
    )
    billing_cycle = models.ForeignKey(
        BillingCycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proration_events",
    )
    change_type = models.CharField(max_length=24, choices=CHANGE_CHOICES)
    # Signed: positive is an extra charge, negative is money owed back to the customer.
    delta_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    effective_date = models.DateField()
    # The inputs the formula ran on (old/new qty, unit price, days remaining, days in
    # cycle) so the arithmetic can be shown on screen, not just asserted.
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proration_event"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.change_type} {self.delta_amount} on {self.effective_date}"
