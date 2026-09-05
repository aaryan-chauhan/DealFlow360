from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Company, TimeStampedModel, UUIDModel
from catalog.models import Product

PCT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class DiscountTier(UUIDModel, TimeStampedModel):
    """The overall discount ceiling per customer tier — admin-configured data, not code,
    so the rules are editable without a redeploy (Screen 18)."""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="discount_tiers"
    )
    name = models.CharField(max_length=64)
    max_discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, validators=PCT_VALIDATORS
    )

    class Meta:
        db_table = "discount_tier"
        ordering = ["max_discount_pct"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="uniq_discount_tier_company_name"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.max_discount_pct}%)"


class CategoryDiscountCeiling(UUIDModel, TimeStampedModel):
    """The stricter, category-specific override. Without this the system could only check
    one flat number per order and an over-discounted Services line would hide inside an
    otherwise-fine Gold order (§5.3, §7.1)."""

    discount_tier = models.ForeignKey(
        DiscountTier, on_delete=models.CASCADE, related_name="category_ceilings"
    )
    category = models.CharField(max_length=32, choices=Product.CATEGORY_CHOICES)
    max_discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, validators=PCT_VALIDATORS
    )

    class Meta:
        db_table = "category_discount_ceiling"
        ordering = ["category"]
        constraints = [
            models.UniqueConstraint(
                fields=["discount_tier", "category"], name="uniq_ceiling_tier_category"
            )
        ]

    def __str__(self):
        return f"{self.discount_tier.name} / {self.category}: {self.max_discount_pct}%"


class ApprovalChainRule(UUIDModel, TimeStampedModel):
    """Maps a risk-score range to a required approval level. Company-wide, not per tier —
    any deal above a threshold needs Finance regardless of the customer's tier (§5.3)."""

    NONE = "none"
    MANAGER = "manager"
    MANAGER_THEN_FINANCE = "manager_then_finance"
    LEVEL_CHOICES = [
        (NONE, "No approval"),
        (MANAGER, "Sales Manager"),
        (MANAGER_THEN_FINANCE, "Sales Manager → Finance"),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="approval_chain_rules"
    )
    discount_range_from = models.DecimalField(
        max_digits=5, decimal_places=2, validators=PCT_VALIDATORS
    )
    discount_range_to = models.DecimalField(
        max_digits=5, decimal_places=2, validators=PCT_VALIDATORS
    )
    required_level = models.CharField(max_length=32, choices=LEVEL_CHOICES, default=MANAGER)

    class Meta:
        db_table = "approval_chain_rule"
        ordering = ["discount_range_from"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(discount_range_to__gt=models.F("discount_range_from")),
                name="chk_approval_rule_range_valid",
            )
        ]

    def __str__(self):
        return f"{self.discount_range_from}–{self.discount_range_to} → {self.required_level}"

    def covers(self, score):
        """Ranges are half-open [from, to) so adjacent rules never both match (§7.1)."""
        return self.discount_range_from <= score < self.discount_range_to
