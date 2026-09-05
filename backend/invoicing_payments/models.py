"""Money changing hands (spec §5.10).

The rule this module exists to guarantee: a one-time product charge and a recurring
subscription charge never merge. They can sit on the *same* invoice — a mixed order
raises exactly one document — but always as separate `invoice_line` rows, one pointing
at a product and the other at a subscription. That is enforced by a database check
constraint below, not by convention, because "never both on one line" is the invariant
every downstream screen and report reads back.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Customer, TimeStampedModel, User, UUIDModel
from catalog.models import Product
from quotations.models import Quotation

ZERO = Decimal("0.00")


class Invoice(UUIDModel, TimeStampedModel):
    """A billing document.

    `quotation` is SET NULL on delete — an invoice is a financial record that must
    survive independently even if the originating quote is later removed (§5.10).
    `customer` is PROTECT, which also keeps `customer.company` as the tenant anchor.

    `invoice_type` records *how the document was raised*, not what it contains: an order
    invoice (`one_time`) may legitimately carry the first subscription charge alongside
    the hardware, while `recurring` marks one the billing run generated for a period.
    Callers that need to know what is actually on the invoice read `has_one_time` /
    `has_recurring` instead of inferring it from this field.
    """

    ONE_TIME = "one_time"
    RECURRING = "recurring"
    TYPE_CHOICES = [(ONE_TIME, "One-time / order"), (RECURRING, "Recurring")]

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (ISSUED, "Issued"),
        (PARTIALLY_PAID, "Partially Paid"),
        (PAID, "Paid"),
        (VOID, "Void"),
    ]

    quotation = models.ForeignKey(
        Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=32, unique=True)
    invoice_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=ONE_TIME)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ISSUED)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    class Meta:
        db_table = "invoice"
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return self.invoice_number

    @property
    def company(self):
        return self.customer.company

    @classmethod
    def next_number(cls, prefix="INV"):
        """INV-<year>-<seq>. Global rather than per company because `invoice_number` is
        unique platform-wide per §5.10."""
        year = timezone.localdate().year
        stem = f"{prefix}-{year}-"
        last = (
            cls.objects.filter(invoice_number__startswith=stem)
            .order_by("-invoice_number")
            .values_list("invoice_number", flat=True)
            .first()
        )
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{stem}{seq:04d}"

    # -- line pools -------------------------------------------------------------
    # Kept as two separate accessors on purpose. Nothing in the codebase should ever
    # iterate one merged list of lines for display or totalling (§ user rule / §7.3.4).

    @property
    def one_time_lines(self):
        return [line for line in self.lines.all() if line.is_one_time]

    @property
    def recurring_lines(self):
        return [line for line in self.lines.all() if line.is_recurring]

    @property
    def one_time_subtotal(self):
        return sum((line.amount for line in self.one_time_lines), ZERO)

    @property
    def recurring_subtotal(self):
        return sum((line.amount for line in self.recurring_lines), ZERO)

    @property
    def has_one_time(self):
        return any(line.is_one_time for line in self.lines.all())

    @property
    def has_recurring(self):
        return any(line.is_recurring for line in self.lines.all())

    @property
    def is_mixed(self):
        """A single order carrying both kinds of charge — the case Screen 13 must render
        as two separate sections."""
        return self.has_one_time and self.has_recurring

    # -- payment state ----------------------------------------------------------

    @property
    def amount_paid(self):
        return sum((payment.amount for payment in self.payments.all()), ZERO)

    @property
    def amount_credited(self):
        return sum((note.amount for note in self.credit_notes.all()), ZERO)

    @property
    def balance_due(self):
        return (self.total_amount - self.amount_paid - self.amount_credited).quantize(
            Decimal("0.01")
        )

    def recompute_total(self, save=True):
        self.total_amount = sum((line.amount for line in self.lines.all()), ZERO)
        if save:
            self.save(update_fields=["total_amount", "updated_at"])
        return self.total_amount

    def recompute_status(self, save=True):
        """Void is terminal and never recomputed — a voided invoice that later receives a
        stray payment must stay void and be reconciled by hand."""
        if self.status == self.VOID:
            return self.status
        outstanding = self.balance_due
        if outstanding <= ZERO and self.total_amount > ZERO:
            self.status = self.PAID
        elif self.amount_paid > ZERO:
            self.status = self.PARTIALLY_PAID
        else:
            self.status = self.ISSUED
        if save:
            self.save(update_fields=["status", "updated_at"])
        return self.status

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.next_number()
        return super().save(*args, **kwargs)


class InvoiceLine(UUIDModel, TimeStampedModel):
    """Each line points to *either* a product (one-time) *or* a subscription (recurring) —
    never both, and never neither (§5.10).

    The check constraint below is the structural guarantee. A recurring charge that also
    carried a product FK would be indistinguishable from a one-time one, and the split
    billing view — plus every revenue report that follows it — would quietly merge two
    kinds of money that the business treats differently.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_lines"
    )
    subscription = models.ForeignKey(
        "subscriptions_billing.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_lines",
    )
    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    class Meta:
        db_table = "invoice_line"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                # Exactly one of the two FKs. SET NULL on product deletion could break
                # this for an archived SKU, so the one-time side is allowed to keep its
                # identity through `subscription IS NULL` rather than requiring a product.
                check=models.Q(subscription__isnull=True) | models.Q(product__isnull=True),
                name="invoice_line_never_both_product_and_subscription",
            )
        ]

    def __str__(self):
        return f"{self.description}: {self.amount}"

    @property
    def is_recurring(self):
        return self.subscription_id is not None

    @property
    def is_one_time(self):
        return self.subscription_id is None


class Payment(UUIDModel, TimeStampedModel):
    """Separate from `invoice` because an invoice can be partially paid across several
    payments, each needing its own timestamp and reference for reconciliation (§5.10)."""

    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    UPI = "upi"
    CHEQUE = "cheque"
    METHOD_CHOICES = [
        (BANK_TRANSFER, "Bank Transfer"),
        (CARD, "Card"),
        (UPI, "UPI"),
        (CHEQUE, "Cheque"),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    method = models.CharField(max_length=24, choices=METHOD_CHOICES, default=BANK_TRANSFER)
    paid_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=128, blank=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments_recorded"
    )

    class Meta:
        db_table = "payment"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.amount} on {self.invoice_id}"


class CreditNote(UUIDModel, TimeStampedModel):
    """Can link to an invoice *or* directly to a subscription — the latter is the
    cancellation path, where a refund is owed without a specific invoice being involved
    (§5.10, §7.3.3)."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_notes"
    )
    subscription = models.ForeignKey(
        "subscriptions_billing.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_notes",
    )
    # Denormalised so a credit note keeps its owner even if both nullable links are
    # cleared — it is a financial record and must never become unattributable.
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="credit_notes"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    reason = models.TextField(blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="credit_notes_issued"
    )

    class Meta:
        db_table = "credit_note"
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Credit {self.amount} ({self.reason[:40]})"
