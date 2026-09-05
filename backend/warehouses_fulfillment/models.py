from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import Company, TimeStampedModel, UUIDModel
from catalog.models import Product
from quotations.models import Quotation

ZERO = Decimal("0.00")


class Warehouse(UUIDModel, TimeStampedModel):
    """A shipping location. `shipping_cost_weight` is what the split optimiser sorts on
    (§5.7) — a relative cost per unit shipped, so the engine can minimise cost as well as
    shipment count instead of blindly picking the nearest site."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="warehouses")
    name = models.CharField(max_length=255)
    shipping_cost_weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(0)],
    )
    # Free-form per-site rules (lead time, reorder point). JSON because every warehouse
    # replenishes differently and this has to stay editable without a migration.
    replenishment_rule = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "warehouse"
        ordering = ["shipping_cost_weight", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="uniq_warehouse_company_name"
            )
        ]

    def __str__(self):
        return self.name


class StockLevel(UUIDModel, TimeStampedModel):
    """Inventory per product *per warehouse* — one product can be in stock at one site and
    backordered at another simultaneously (§5.7)."""

    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stock_levels"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_levels")
    qty_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    qty_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    # Stored so the replenishment watcher can filter on it in SQL, but always re-derived
    # on write so on-hand/reserved/available can never drift apart.
    qty_available = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)

    class Meta:
        db_table = "stock_level"
        ordering = ["warehouse__shipping_cost_weight", "product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "product"], name="uniq_stock_warehouse_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.qty_available}"

    def save(self, *args, **kwargs):
        self.qty_available = self.qty_on_hand - self.qty_reserved
        update_fields = kwargs.get("update_fields")
        if update_fields:
            kwargs["update_fields"] = {*update_fields, "qty_available", "updated_at"}
        return super().save(*args, **kwargs)

    def reserve(self, qty):
        self.qty_reserved += Decimal(qty)
        self.save(update_fields=["qty_reserved"])

    def release(self, qty):
        # Clamped at zero so a release can never invent stock if the two sides ever
        # disagree after a manual admin edit.
        self.qty_reserved = max(ZERO, self.qty_reserved - Decimal(qty))
        self.save(update_fields=["qty_reserved"])


class FulfillmentOrder(UUIDModel, TimeStampedModel):
    """Opened automatically once a quotation is approved/confirmed (§11). `promised_date`
    feeds the delivery-slippage alert in Deal Health (§5.7)."""

    SUGGESTED = "suggested"
    ACCEPTED = "accepted"
    BACKORDERED = "backordered"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (SUGGESTED, "Split Suggested"),
        (ACCEPTED, "Split Accepted"),
        (BACKORDERED, "Partially Backordered"),
        (FULFILLED, "Fulfilled"),
        (CANCELLED, "Cancelled"),
    ]
    # Once stock is reserved the suggestion is no longer free to silently re-plan itself.
    RESERVED_STATUSES = {ACCEPTED, BACKORDERED, FULFILLED}

    quotation = models.OneToOneField(
        Quotation, on_delete=models.CASCADE, related_name="fulfillment_order"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=SUGGESTED)
    promised_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "fulfillment_order"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quotation.number} ({self.status})"

    @property
    def has_backorder(self):
        return any(line.is_backorder for line in self.split_lines.all())

    @property
    def shipment_count(self):
        """Distinct warehouses actually shipping — the number the optimiser minimises.
        Counting split lines instead would double-count a site sending two products."""
        return len(
            {line.warehouse_id for line in self.split_lines.all() if not line.is_backorder}
        )

    @property
    def open_backorder_event(self):
        return self.backorder_events.filter(resolved=False).first()


class WarehouseSplitLine(UUIDModel, TimeStampedModel):
    """The actual split decision ("6 units from Mumbai, 4 from Bangalore"), one row per
    (warehouse, product). A shortfall is written as its own line with `is_backorder=True`
    against the preferred warehouse, so the outstanding quantity stays a real number the
    consolidation watcher can compare against incoming stock (§5.7, §7.2)."""

    fulfillment_order = models.ForeignKey(
        FulfillmentOrder, on_delete=models.CASCADE, related_name="split_lines"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="split_lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="split_lines")
    qty_fulfilled = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    est_shipment_count = models.PositiveSmallIntegerField(default=1)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    is_backorder = models.BooleanField(default=False)
    # Set by the replenishment watcher when stock catches up. Never applied silently — it
    # only lights up the "Consolidate Remaining Backorder" prompt (§7.2.6).
    consolidation_available = models.BooleanField(default=False)
    is_override = models.BooleanField(default=False)

    class Meta:
        db_table = "warehouse_split_line"
        ordering = ["is_backorder", "product__name", "warehouse__shipping_cost_weight"]

    def __str__(self):
        suffix = " (backorder)" if self.is_backorder else ""
        return f"{self.product.name} x{self.qty_fulfilled} @ {self.warehouse.name}{suffix}"


class BackorderEvent(UUIDModel):
    """Logs when a backorder was raised and resolved. A backorder is not a single state —
    it can be triggered and partially resolved repeatedly as stock trickles in (§5.7)."""

    fulfillment_order = models.ForeignKey(
        FulfillmentOrder, on_delete=models.CASCADE, related_name="backorder_events"
    )
    triggered_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)
    customer_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "backorder_event"
        ordering = ["-triggered_at"]

    def __str__(self):
        state = "resolved" if self.resolved else "open"
        return f"{self.fulfillment_order_id} backorder ({state})"
