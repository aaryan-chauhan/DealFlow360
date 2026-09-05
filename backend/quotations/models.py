from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Company, Customer, TimeStampedModel, User, UUIDModel
from catalog.models import Product, ProductVariant


class Quotation(UUIDModel, TimeStampedModel):
    """The deal record — the centre of the schema. Every other module keys off it."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    NEGOTIATION = "negotiation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PENDING_APPROVAL, "Pending Approval"),
        (APPROVED, "Approved"),
        (NEGOTIATION, "Negotiation"),
        (CONFIRMED, "Confirmed"),
        (REJECTED, "Rejected"),
    ]
    # Statuses whose lines may still be edited; an edit here re-runs the risk engine.
    EDITABLE_STATUSES = {DRAFT, PENDING_APPROVAL, NEGOTIATION}

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="quotations")
    number = models.CharField(max_length=32)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="quotations")
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="quotations")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=DRAFT)
    # Cached, not computed on read: expensive, must display instantly, and only changes
    # when a line, discount or negotiation changes (§5.4).
    blended_risk_score = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    # Cached beside the blended score for the same reason (§5.4). Routing uses the
    # *greater* of the two (§7.1), so without this every screen that wants to show the
    # number that actually decided approval would have to re-run the engine on read.
    max_single_overage = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    valid_till = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "quotation"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="uniq_quotation_company_number")
        ]

    def __str__(self):
        return self.number

    @property
    def routing_score(self):
        """The number the approval chain is matched against (§7.1) — the greater of the
        blended average and the worst single line, so one badly-over line can never hide
        inside an otherwise-low average. This is the score every screen should headline."""
        return max(self.blended_risk_score, self.max_single_overage)

    @property
    def total_value(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0.00"))

    @property
    def average_discount_pct(self):
        lines = list(self.lines.all())
        gross = sum((line.qty * line.unit_price for line in lines), Decimal("0.00"))
        if gross <= 0:
            return Decimal("0.00")
        net = sum((line.line_total for line in lines), Decimal("0.00"))
        return ((gross - net) / gross * 100).quantize(Decimal("0.01"))

    @classmethod
    def next_number(cls, company):
        """Q-<year>-<seq> per company, matching the wireframe's Q-2026-001."""
        year = timezone.now().year
        prefix = f"Q-{year}-"
        last = (
            cls.objects.filter(company=company, number__startswith=prefix)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:03d}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.next_number(self.company)
        if not self.valid_till:
            self.valid_till = (timezone.now() + timedelta(days=15)).date()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def set_status(self, new_status, changed_by=None):
        """Every transition is logged — "who moved this to Pending Approval, and when"."""
        if new_status == self.status:
            return None
        history = QuotationStatusHistory.objects.create(
            quotation=self, from_status=self.status, to_status=new_status, changed_by=changed_by
        )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        return history


class QuotationLine(UUIDModel, TimeStampedModel):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    LINE_TYPE_CHOICES = [(ONE_TIME, "One-time"), (RECURRING, "Recurring")]

    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="quotation_lines")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotation_lines"
    )
    qty = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    # Snapshot at add-time, never a live join to price_list_item: if pricing changes
    # tomorrow it must not silently change a quote already under negotiation (§5.4).
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    line_type = models.CharField(max_length=16, choices=LINE_TYPE_CHOICES, default=ONE_TIME)

    class Meta:
        db_table = "quotation_line"
        ordering = ["created_at"]
        # One row per (product, variant) per quote. Two constraints rather than one
        # because Postgres treats NULLs as distinct in a unique index, so a plain
        # three-column constraint would happily allow the same product twice whenever
        # `variant` is null — which is the common case.
        constraints = [
            models.UniqueConstraint(
                fields=["quotation", "product", "variant"],
                condition=models.Q(variant__isnull=False),
                name="uniq_line_quotation_product_variant",
            ),
            models.UniqueConstraint(
                fields=["quotation", "product"],
                condition=models.Q(variant__isnull=True),
                name="uniq_line_quotation_product_no_variant",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} x{self.qty}"

    def compute_total(self):
        return (self.qty * self.unit_price * (1 - self.discount_pct / 100)).quantize(
            Decimal("0.01")
        )

    def save(self, *args, **kwargs):
        self.line_total = self.compute_total()
        return super().save(*args, **kwargs)


class QuotationStatusHistory(UUIDModel):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=32)
    to_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="quotation_status_changes"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quotation_status_history"
        ordering = ["changed_at"]

    def __str__(self):
        return f"{self.quotation_id}: {self.from_status} → {self.to_status}"
