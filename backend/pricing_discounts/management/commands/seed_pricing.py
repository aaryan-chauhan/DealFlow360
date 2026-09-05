"""Seeds the discount-governance slice of spec §13: tier ceilings, the stricter
per-category ceilings, and the company-wide approval chain ranges. Idempotent."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company
from catalog.models import Product
from pricing_discounts.models import ApprovalChainRule, CategoryDiscountCeiling, DiscountTier

COMPANY_NAME = "Acme Solutions"

TIERS = [
    ("Bronze", Decimal("5.00")),
    ("Silver", Decimal("10.00")),
    ("Gold", Decimal("15.00")),
]

# The stricter, category-specific override applied to every tier (§5.3). The effective
# ceiling for a line is min(tier ceiling, category ceiling).
CATEGORY_CEILINGS = [
    (Product.HARDWARE, Decimal("15.00")),
    (Product.SOFTWARE, Decimal("10.00")),
    (Product.SERVICES, Decimal("10.00")),
]

# Half-open ranges [from, to) over the routing score from §7.1.
CHAIN_RULES = [
    (Decimal("0.00"), Decimal("10.00"), ApprovalChainRule.MANAGER),
    (Decimal("10.00"), Decimal("100.00"), ApprovalChainRule.MANAGER_THEN_FINANCE),
]


class Command(BaseCommand):
    help = "Seed discount tiers, category ceilings and approval chain rules."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(
                f"Company '{COMPANY_NAME}' not found. Run `manage.py seed_accounts` first."
            )

        for name, max_pct in TIERS:
            tier, created = DiscountTier.objects.get_or_create(
                company=company, name=name, defaults={"max_discount_pct": max_pct}
            )
            self.stdout.write(
                f"{'created' if created else 'reused '}  tier      {tier.name} "
                f"max {tier.max_discount_pct}%"
            )

            for category, ceiling_pct in CATEGORY_CEILINGS:
                ceiling, c_created = CategoryDiscountCeiling.objects.get_or_create(
                    discount_tier=tier,
                    category=category,
                    defaults={"max_discount_pct": ceiling_pct},
                )
                if c_created:
                    self.stdout.write(
                        f"          ceiling   {tier.name} / {category}: "
                        f"{ceiling.max_discount_pct}%"
                    )

        for start, end, level in CHAIN_RULES:
            rule, created = ApprovalChainRule.objects.get_or_create(
                company=company,
                discount_range_from=start,
                discount_range_to=end,
                defaults={"required_level": level},
            )
            # ASCII only: management output has to survive a cp1252 Windows console.
            self.stdout.write(
                f"{'created' if created else 'reused '}  chain     {rule.discount_range_from}-"
                f"{rule.discount_range_to} -> {rule.required_level}"
            )

        self.stdout.write(self.style.SUCCESS("\nDone."))
