"""Seeds the catalog slice of spec §13: sample products across Hardware/Software/Services,
their variants, and an INR price book with per-tier prices. Idempotent."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company
from catalog.models import PriceList, PriceListItem, Product, ProductVariant

COMPANY_NAME = "Acme Solutions"
PRICE_LIST = ("India, INR", "INR")

# name, category, base_price, is_subscription, unit, tax_pct, description
PRODUCTS = [
    (
        "Dell Latitude 5440",
        Product.HARDWARE,
        Decimal("80000.00"),
        False,
        "unit",
        Decimal("18.00"),
        "14\" business laptop, i7 / 16GB / 512GB SSD.",
    ),
    (
        "Microsoft 365 Business",
        Product.SOFTWARE,
        Decimal("12000.00"),
        True,
        "seat/year",
        Decimal("18.00"),
        "Annual productivity suite licence, per seat.",
    ),
    (
        "Extended Warranty",
        Product.SERVICES,
        Decimal("5000.00"),
        False,
        "unit",
        Decimal("18.00"),
        "Two-year parts and labour cover on hardware.",
    ),
    (
        "Onsite Support Plan",
        Product.SERVICES,
        Decimal("8000.00"),
        True,
        "month",
        Decimal("18.00"),
        "Monthly onsite engineer visits with 4-hour response.",
    ),
    (
        "Training & Onboarding",
        Product.SERVICES,
        Decimal("10000.00"),
        False,
        "session",
        Decimal("18.00"),
        "Half-day rollout training for up to 20 staff.",
    ),
    (
        "HP EliteBook 840",
        Product.HARDWARE,
        Decimal("95000.00"),
        False,
        "unit",
        Decimal("18.00"),
        "14\" premium business laptop, i7 / 16GB / 512GB SSD.",
    ),
    (
        "Cloud Backup Service",
        Product.SOFTWARE,
        Decimal("6000.00"),
        True,
        "seat/year",
        Decimal("18.00"),
        "Automated cloud backup & disaster recovery, per seat annual licence.",
    ),
]

VARIANTS = {
    "Dell Latitude 5440": [
        ("RAM", "8GB", Decimal("0.00")),
        ("RAM", "16GB", Decimal("8000.00")),
        ("Storage", "512GB SSD", Decimal("0.00")),
        ("Storage", "1TB SSD", Decimal("6000.00")),
    ],
    "Microsoft 365 Business": [
        ("Plan", "Standard", Decimal("0.00")),
        ("Plan", "Premium", Decimal("4000.00")),
    ],
}

# Tier price books: Bronze pays list, better tiers get a standing discount off base.
TIER_MULTIPLIERS = [("Bronze", Decimal("1.00")), ("Silver", Decimal("0.97")), ("Gold", Decimal("0.95"))]


class Command(BaseCommand):
    help = "Seed demo products, variants and an INR price list."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(
                f"Company '{COMPANY_NAME}' not found. Run `manage.py seed_accounts` first."
            )

        price_list, created = PriceList.objects.get_or_create(
            company=company, name=PRICE_LIST[0], defaults={"currency": PRICE_LIST[1]}
        )
        self.stdout.write(f"{'created' if created else 'reused '}  price list  {price_list}")

        for name, category, base_price, is_sub, unit, tax, description in PRODUCTS:
            product, created = Product.objects.get_or_create(
                company=company,
                name=name,
                defaults={
                    "category": category,
                    "base_price": base_price,
                    "is_subscription": is_sub,
                    "unit": unit,
                    "tax_pct": tax,
                    "description": description,
                },
            )
            self.stdout.write(
                f"{'created' if created else 'reused '}  product     {product.name} "
                f"({product.category}, {product.base_price})"
            )

            for attribute, value, extra in VARIANTS.get(name, []):
                ProductVariant.objects.get_or_create(
                    product=product,
                    attribute=attribute,
                    value=value,
                    defaults={"extra_price": extra},
                )

            for tier, multiplier in TIER_MULTIPLIERS:
                PriceListItem.objects.get_or_create(
                    price_list=price_list,
                    product=product,
                    tier=tier,
                    defaults={
                        "price_rule": PriceListItem.FIXED,
                        "price": (product.base_price * multiplier).quantize(Decimal("0.01")),
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {Product.objects.filter(company=company).count()} products, "
                f"{ProductVariant.objects.filter(product__company=company).count()} variants, "
                f"{PriceListItem.objects.filter(price_list=price_list).count()} price rows."
            )
        )
