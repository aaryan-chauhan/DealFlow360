from django.contrib import admin

from .models import (
    BackorderEvent,
    FulfillmentOrder,
    StockLevel,
    Warehouse,
    WarehouseSplitLine,
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "shipping_cost_weight"]
    list_filter = ["company"]


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    """The fastest way to simulate a replenishment: bump `qty_on_hand` here, then run the
    scan (`POST /api/fulfillment/scan-replenishment`) to light up consolidation."""

    list_display = ["product", "warehouse", "qty_on_hand", "qty_reserved", "qty_available"]
    list_filter = ["warehouse"]
    search_fields = ["product__name"]
    readonly_fields = ["qty_available"]


class WarehouseSplitLineInline(admin.TabularInline):
    model = WarehouseSplitLine
    extra = 0
    readonly_fields = ["cost", "est_shipment_count"]


@admin.register(FulfillmentOrder)
class FulfillmentOrderAdmin(admin.ModelAdmin):
    list_display = ["quotation", "status", "promised_date", "created_at"]
    list_filter = ["status"]
    inlines = [WarehouseSplitLineInline]


@admin.register(BackorderEvent)
class BackorderEventAdmin(admin.ModelAdmin):
    list_display = ["fulfillment_order", "triggered_at", "resolved", "customer_notified_at"]
    list_filter = ["resolved"]
