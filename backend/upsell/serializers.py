from rest_framework import serializers

from catalog.models import Product

from .models import Suggestion, UpsellRule


class UpsellRuleSerializer(serializers.ModelSerializer):
    source_product_name = serializers.CharField(source="source_product.name", read_only=True)
    recommended_product_name = serializers.CharField(source="recommended_product.name", read_only=True)

    class Meta:
        model = UpsellRule
        fields = [
            "id",
            "source_product",
            "source_product_name",
            "recommended_product",
            "recommended_product_name",
            "co_purchase_score",
            "is_promoted",
            "min_margin_pct",
            "created_at",
        ]


class SuggestionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_category = serializers.CharField(source="product.category", read_only=True)
    base_price = serializers.DecimalField(source="product.base_price", max_digits=12, decimal_places=2, read_only=True)
    co_purchase_score = serializers.DecimalField(source="upsell_rule.co_purchase_score", max_digits=5, decimal_places=2, read_only=True)
    is_promoted = serializers.BooleanField(source="upsell_rule.is_promoted", read_only=True)

    class Meta:
        model = Suggestion
        fields = [
            "id",
            "quotation",
            "product",
            "product_name",
            "product_category",
            "base_price",
            "margin_delta",
            "co_purchase_score",
            "is_promoted",
            "status",
            "created_at",
        ]
