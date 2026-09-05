from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Company, TimeStampedModel, UUIDModel
from catalog.models import Product

ZERO = Decimal("0.00")
PCT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class UpsellRule(UUIDModel, TimeStampedModel):
    """Admin-configured cross-sell pairing logic (spec §5.6, §7.4).
    
    `min_margin_pct` exists specifically so low-margin suggestions never surface, per the
    requirement that only healthy-margin upsells appear.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="upsell_rules")
    source_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="upsell_source_rules"
    )
    recommended_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="upsell_target_rules"
    )
    co_purchase_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("50.00"), validators=PCT_VALIDATORS
    )
    is_promoted = models.BooleanField(default=False)
    min_margin_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("15.00"), validators=PCT_VALIDATORS
    )

    class Meta:
        db_table = "upsell_rule"
        ordering = ["-is_promoted", "-co_purchase_score"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "source_product", "recommended_product"],
                name="uniq_upsell_rule_pair",
            )
        ]

    def __str__(self):
        return f"{self.source_product.name} -> {self.recommended_product.name} (score: {self.co_purchase_score})"


class Suggestion(UUIDModel, TimeStampedModel):
    """The suggestion shown on a specific quotation, tracked separately to record whether
    the rep added or dismissed it (§5.6, §7.4).
    """

    SUGGESTED = "Suggested"
    ADDED = "Added"
    DISMISSED = "Dismissed"
    STATUS_CHOICES = [
        (SUGGESTED, "Suggested"),
        (ADDED, "Added"),
        (DISMISSED, "Dismissed"),
    ]

    quotation = models.ForeignKey(
        "quotations.Quotation", on_delete=models.CASCADE, related_name="suggestions"
    )
    upsell_rule = models.ForeignKey(
        UpsellRule, on_delete=models.PROTECT, related_name="suggestions"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="suggestions")
    margin_delta = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=SUGGESTED)

    class Meta:
        db_table = "suggestion"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["quotation", "upsell_rule"], name="uniq_suggestion_quotation_rule"
            )
        ]

    def __str__(self):
        return f"{self.product.name} on {self.quotation.number} ({self.status})"
