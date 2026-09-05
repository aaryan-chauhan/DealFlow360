from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    FulfillmentViewSet,
    ReplenishmentScanView,
    StockLevelAdminViewSet,
    WarehouseAdminViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("fulfillment", FulfillmentViewSet, basename="fulfillment")
router.register("warehouses", WarehouseAdminViewSet, basename="warehouse")
router.register("stock-levels", StockLevelAdminViewSet, basename="stock-level")

# §8 puts the list on /api/fulfillment/orders but the detail on /api/fulfillment/{id}.
# The literal routes are declared first, and the viewset pins its lookup to a UUID, so
# "orders" and "scan-replenishment" can never be mistaken for a primary key.
urlpatterns = [
    path(
        "fulfillment/orders",
        FulfillmentViewSet.as_view({"get": "list"}),
        name="fulfillment-orders",
    ),
    path(
        "fulfillment/scan-replenishment",
        ReplenishmentScanView.as_view(),
        name="fulfillment-scan-replenishment",
    ),
    *router.urls,
]

