from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import PriceListItemViewSet, PriceListViewSet, ProductVariantViewSet, ProductViewSet

router = SimpleRouter(trailing_slash=False)
router.register("products", ProductViewSet, basename="product")
router.register("price-lists", PriceListViewSet, basename="price-list")

variant_list = ProductVariantViewSet.as_view({"get": "list", "post": "create"})
variant_detail = ProductVariantViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
price_item_list = PriceListItemViewSet.as_view({"get": "list", "post": "create"})
price_item_detail = PriceListItemViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path("products/<uuid:product_id>/variants", variant_list, name="product-variants"),
    path("products/<uuid:product_id>/variants/<uuid:pk>", variant_detail, name="product-variant"),
    path("price-lists/<uuid:price_list_id>/items", price_item_list, name="price-list-items"),
    path("price-lists/<uuid:price_list_id>/items/<uuid:pk>", price_item_detail, name="price-list-item"),
    *router.urls,
]
