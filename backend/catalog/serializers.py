from rest_framework import serializers

from .models import PriceList, PriceListItem, Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "product", "product_name", "attribute", "value", "extra_price"]
        read_only_fields = ["product"]


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    variant_count = serializers.IntegerField(source="variants.count", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "category",
            "is_subscription",
            "description",
            "base_price",
            "tax_pct",
            "unit",
            "is_active",
            "variants",
            "variant_count",
            "created_at",
        ]

    def validate_name(self, value):
        company = self.context["membership"].company
        qs = Product.objects.filter(company=company, name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A product with this name already exists.")
        return value.strip()


class PriceListItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PriceListItem
        fields = ["id", "price_list", "product", "product_name", "tier", "price_rule", "price"]
        read_only_fields = ["price_list"]

    def validate_product(self, value):
        if value.company_id != self.context["membership"].company_id:
            raise serializers.ValidationError("Product belongs to another company.")
        return value


class PriceListSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = PriceList
        fields = ["id", "name", "currency", "item_count", "created_at"]
