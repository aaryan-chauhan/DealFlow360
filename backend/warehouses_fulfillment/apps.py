from django.apps import AppConfig


class WarehousesFulfillmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "warehouses_fulfillment"

    def ready(self):
        # Registers the quotation status listener that auto-opens a FulfillmentOrder the
        # moment a quote reaches approved/confirmed (§11).
        from . import signals  # noqa: F401
