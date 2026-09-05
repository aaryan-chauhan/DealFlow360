from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsAdminOrReadOnly
from accounts.scoping import get_membership

from .models import PriceList, PriceListItem, Product, ProductVariant
from .serializers import (
    PriceListItemSerializer,
    PriceListSerializer,
    ProductSerializer,
    ProductVariantSerializer,
)


class CompanyScopedViewSet(viewsets.ModelViewSet):
    """Every queryset is filtered to the acting company (§12) — never UI-only hiding."""

    permission_classes = [IsAdminOrReadOnly]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}


class ProductViewSet(CompanyScopedViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.filter(company=self.membership.company).prefetch_related("variants")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company)


class ProductVariantViewSet(CompanyScopedViewSet):
    serializer_class = ProductVariantSerializer

    def get_product(self):
        return get_object_or_404(
            Product, pk=self.kwargs["product_id"], company=self.membership.company
        )

    def get_queryset(self):
        return ProductVariant.objects.filter(product=self.get_product())

    def perform_create(self, serializer):
        serializer.save(product=self.get_product())


class PriceListViewSet(CompanyScopedViewSet):
    serializer_class = PriceListSerializer

    def get_queryset(self):
        return PriceList.objects.filter(company=self.membership.company)

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company)


class PriceListItemViewSet(CompanyScopedViewSet):
    serializer_class = PriceListItemSerializer

    def get_price_list(self):
        return get_object_or_404(
            PriceList, pk=self.kwargs["price_list_id"], company=self.membership.company
        )

    def get_queryset(self):
        return PriceListItem.objects.filter(price_list=self.get_price_list()).select_related(
            "product"
        )

    def perform_create(self, serializer):
        serializer.save(price_list=self.get_price_list())
