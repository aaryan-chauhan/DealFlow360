from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    BillingDetailView,
    BillingRunView,
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("subscription-plans", SubscriptionPlanViewSet, basename="subscription-plan")

# `billing/run` is declared before `billing/{id}` so the literal can never be read as a
# primary key — the same ordering the fulfillment routes use.
urlpatterns = [
    path("billing/run", BillingRunView.as_view(), name="billing-run"),
    path("billing/<uuid:pk>", BillingDetailView.as_view(), name="billing-detail"),
    *router.urls,
]
