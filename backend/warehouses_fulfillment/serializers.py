from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product

from .models import (
    BackorderEvent,
    FulfillmentOrder,
    StockLevel,
    Warehouse,
    WarehouseSplitLine,
)
from .services import quotation_demand


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "shipping_cost_weight", "replenishment_rule"]


class SplitLineSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = WarehouseSplitLine
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "product",
            "product_name",
            "qty_fulfilled",
            "est_shipment_count",
            "cost",
            "is_backorder",
            "consolidation_available",
            "is_override",
        ]


class BackorderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackorderEvent
        fields = [
            "id",
            "triggered_at",
            "resolved",
            "resolution_note",
            "customer_notified_at",
        ]


class FulfillmentOrderListSerializer(serializers.ModelSerializer):
    quotation_number = serializers.CharField(source="quotation.number", read_only=True)
    quotation_status = serializers.CharField(source="quotation.status", read_only=True)
    customer_name = serializers.CharField(source="quotation.customer.name", read_only=True)
    owner_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    total_value = serializers.SerializerMethodField()
    shipment_count = serializers.IntegerField(read_only=True)
    has_backorder = serializers.BooleanField(read_only=True)
    warehouse_count = serializers.SerializerMethodField()
    warehouse_names = serializers.SerializerMethodField()

    class Meta:
        model = FulfillmentOrder
        fields = [
            "id",
            "quotation",
            "quotation_number",
            "quotation_status",
            "customer_name",
            "owner_name",
            "status",
            "status_label",
            "promised_date",
            "total_value",
            "shipment_count",
            "warehouse_count",
            "warehouse_names",
            "has_backorder",
            "created_at",
        ]

    def get_owner_name(self, order):
        owner = order.quotation.owner
        return owner.full_name or owner.email

    def get_total_value(self, order):
        return str(order.quotation.total_value)

    def get_warehouse_count(self, order):
        return len({line.warehouse_id for line in order.split_lines.all()})

    def get_warehouse_names(self, order):
        """The sites actually shipping, cheapest first. Backorder lines are excluded —
        they name a warehouse we intend to ship from later, not one that is shipping."""
        seen = {}
        for line in order.split_lines.all():
            if not line.is_backorder:
                seen[line.warehouse_id] = line.warehouse
        return [
            warehouse.name
            for warehouse in sorted(seen.values(), key=lambda w: w.shipping_cost_weight)
        ]


class FulfillmentOrderDetailSerializer(FulfillmentOrderListSerializer):
    """Adds the split table the way Screen 8 renders it: one row per product, a column per
    warehouse. The matrix is built server-side so the UI never has to re-derive which
    warehouses are in play or what is still short."""

    split_lines = SplitLineSerializer(many=True, read_only=True)
    warehouses = serializers.SerializerMethodField()
    rows = serializers.SerializerMethodField()
    backorder_events = BackorderEventSerializer(many=True, read_only=True)
    open_backorder = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta(FulfillmentOrderListSerializer.Meta):
        fields = FulfillmentOrderListSerializer.Meta.fields + [
            "split_lines",
            "warehouses",
            "rows",
            "backorder_events",
            "open_backorder",
            "can_manage",
        ]

    def _warehouses(self, order):
        return list(Warehouse.objects.filter(company=order.quotation.company))

    def get_warehouses(self, order):
        return WarehouseSerializer(self._warehouses(order), many=True).data

    def get_rows(self, order):
        warehouses = self._warehouses(order)
        demand = quotation_demand(order.quotation)
        lines = list(order.split_lines.select_related("warehouse", "product"))

        stock = {
            (level.product_id, level.warehouse_id): level
            for level in StockLevel.objects.filter(warehouse__in=warehouses)
        }

        rows = []
        for product, qty_needed in demand.items():
            product_lines = [line for line in lines if line.product_id == product.id]
            backorder = next((line for line in product_lines if line.is_backorder), None)
            allocations = []
            for warehouse in warehouses:
                line = next(
                    (
                        item
                        for item in product_lines
                        if item.warehouse_id == warehouse.id and not item.is_backorder
                    ),
                    None,
                )
                level = stock.get((product.id, warehouse.id))
                # Once accepted, `qty_available` already excludes this order's own hold, so
                # the override form adds it back — otherwise re-editing an accepted split
                # would look like the stock had vanished. A suggested order holds nothing,
                # so adding it back there would invent stock that does not exist.
                own_reserved = (
                    Decimal(line.qty_fulfilled)
                    if line and order.status in FulfillmentOrder.RESERVED_STATUSES
                    else Decimal("0.00")
                )
                on_hand = level.qty_on_hand if level else Decimal("0.00")
                available = (level.qty_available if level else Decimal("0.00")) + own_reserved
                allocations.append(
                    {
                        "warehouse": str(warehouse.id),
                        "warehouse_name": warehouse.name,
                        "split_line": str(line.id) if line else None,
                        "qty": str(line.qty_fulfilled if line else Decimal("0.00")),
                        "cost": str(line.cost if line else Decimal("0.00")),
                        "qty_on_hand": str(on_hand),
                        "qty_available": str(available),
                    }
                )
            rows.append(
                {
                    "product": str(product.id),
                    "product_name": product.name,
                    "category": product.category,
                    "unit": product.unit,
                    "qty_needed": str(qty_needed),
                    "qty_allocated": str(
                        sum(
                            (line.qty_fulfilled for line in product_lines if not line.is_backorder),
                            Decimal("0.00"),
                        )
                    ),
                    "qty_backordered": str(
                        backorder.qty_fulfilled if backorder else Decimal("0.00")
                    ),
                    "is_backorder": backorder is not None,
                    "backorder_line": str(backorder.id) if backorder else None,
                    "consolidation_available": bool(
                        backorder and backorder.consolidation_available
                    ),
                    "is_override": any(line.is_override for line in product_lines),
                    "allocations": allocations,
                }
            )
        return rows

    def get_open_backorder(self, order):
        event = order.open_backorder_event
        return BackorderEventSerializer(event).data if event else None

    def get_can_manage(self, order):
        """Whether this viewer may accept/override/consolidate. The UI disables its
        buttons off this; the API re-checks it independently (§12)."""
        from accounts.models import Role

        membership = self.context.get("membership")
        return membership is not None and membership.role.code in {
            Role.FINANCE_OPS,
            Role.ADMIN,
        }


class OverrideLineSerializer(serializers.Serializer):
    warehouse = serializers.UUIDField()
    product = serializers.UUIDField()
    qty = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class OverrideSerializer(serializers.Serializer):
    """Resolves the posted UUIDs to company-scoped objects before the service sees them —
    a warehouse from another tenant must fail here, not deep inside the allocator."""

    lines = OverrideLineSerializer(many=True, allow_empty=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_lines(self, lines):
        company = self.context["company"]
        warehouses = {w.id: w for w in Warehouse.objects.filter(company=company)}
        products = {p.id: p for p in Product.objects.filter(company=company)}

        resolved = []
        for entry in lines:
            warehouse = warehouses.get(entry["warehouse"])
            product = products.get(entry["product"])
            if warehouse is None:
                raise serializers.ValidationError("Unknown warehouse for this company.")
            if product is None:
                raise serializers.ValidationError("Unknown product for this company.")
            resolved.append({"warehouse": warehouse, "product": product, "qty": entry["qty"]})
        return resolved


class ConsolidateSerializer(serializers.Serializer):
    # Omit to consolidate every flagged line on the order.
    line_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class NotifySerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")
