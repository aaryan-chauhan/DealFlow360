from django.apps import AppConfig


class SubscriptionsBillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "subscriptions_billing"

    def ready(self):
        # Registers the quotation status listener that provisions subscriptions and
        # raises the order invoice once a quote reaches approved/confirmed (§11).
        from . import signals  # noqa: F401
