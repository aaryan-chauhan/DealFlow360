from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import Company, TimeStampedModel, UUIDModel


class Product(UUIDModel, TimeStampedModel):
    """The sellable item. `category` is what the blended risk engine (§7.1) looks up on
    every quotation line to find the correct discount ceiling."""

    HARDWARE = "Hardware"
    SOFTWARE = "Software"
    SERVICES = "Services"
    SUBSCRIPTION = "Subscription"
    CATEGORY_CHOICES = [
        (HARDWARE, HARDWARE),
        (SOFTWARE, SOFTWARE),
        (SERVICES, SERVICES),
        (SUBSCRIPTION, SUBSCRIPTION),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    is_subscription = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    # Anchor/list price shown on the catalog screen. The *sell* price for a given
    # price book and customer tier lives on `price_list_item`.
    base_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    tax_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    unit = models.CharField(max_length=32, default="unit")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_product_company_name")
        ]

    def __str__(self):
        return self.name


class ProductVariant(UUIDModel, TimeStampedModel):
    """"RAM: 16GB (+₹8,000)" style options, kept off `product` so one product can carry
    many attribute combinations without duplicating the row."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=64)
    value = models.CharField(max_length=64)
    extra_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "product_variant"
        ordering = ["attribute", "value"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "attribute", "value"], name="uniq_variant_product_attr_value"
            )
        ]

    def __str__(self):
        return f"{self.attribute}: {self.value}"


class PriceList(UUIDModel, TimeStampedModel):
    """A named price book (e.g. "India, INR"). Pricing varies by currency/segment, so it
    is not a fixed attribute of the product."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="price_lists")
    name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        db_table = "price_list"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_price_list_company_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"


class PriceListItem(UUIDModel, TimeStampedModel):
    """The sell price for a product on a given list, for a given customer tier."""

    FIXED = "fixed"
    PERCENT_OFF_BASE = "percent_off_base"
    PRICE_RULE_CHOICES = [
        (FIXED, "Fixed price"),
        (PERCENT_OFF_BASE, "Percent off base price"),
    ]

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_list_items"
    )
    # Free text rather than an FK: tiers are admin-configurable rows in
    # `discount_tier`, and a price book may carry a tier that was later renamed.
    tier = models.CharField(max_length=32)
    price_rule = models.CharField(max_length=32, choices=PRICE_RULE_CHOICES, default=FIXED)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = "price_list_item"
        ordering = ["product__name", "tier"]
        constraints = [
            models.UniqueConstraint(
                fields=["price_list", "product", "tier"], name="uniq_price_item_list_product_tier"
            )
        ]

    def __str__(self):
        return f"{self.product.name} / {self.tier}: {self.price}"
