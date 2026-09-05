from rest_framework import serializers

from .models import ApprovalChainRule, CategoryDiscountCeiling, DiscountTier


class CategoryDiscountCeilingSerializer(serializers.ModelSerializer):
    discount_tier_name = serializers.CharField(source="discount_tier.name", read_only=True)

    class Meta:
        model = CategoryDiscountCeiling
        fields = ["id", "discount_tier", "discount_tier_name", "category", "max_discount_pct"]

    def validate_discount_tier(self, value):
        if value.company_id != self.context["membership"].company_id:
            raise serializers.ValidationError("Discount tier belongs to another company.")
        return value


class DiscountTierSerializer(serializers.ModelSerializer):
    category_ceilings = CategoryDiscountCeilingSerializer(many=True, read_only=True)
    approval_chain = serializers.SerializerMethodField()

    class Meta:
        model = DiscountTier
        fields = ["id", "name", "max_discount_pct", "category_ceilings", "approval_chain"]

    def get_approval_chain(self, tier):
        """Screen 18 shows the chain a tier's ceiling would trigger. It is *derived* —
        approval policy is company-wide (§5.3), not a column on the tier."""
        for rule in self.context.get("approval_rules", []):
            if rule.covers(tier.max_discount_pct):
                return {
                    "level": rule.required_level,
                    "label": rule.get_required_level_display(),
                }
        return {"level": ApprovalChainRule.NONE, "label": "No approval"}

    def validate_name(self, value):
        company = self.context["membership"].company
        qs = DiscountTier.objects.filter(company=company, name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A tier with this name already exists.")
        return value.strip()


class ApprovalChainRuleSerializer(serializers.ModelSerializer):
    required_level_display = serializers.CharField(
        source="get_required_level_display", read_only=True
    )

    class Meta:
        model = ApprovalChainRule
        fields = [
            "id",
            "discount_range_from",
            "discount_range_to",
            "required_level",
            "required_level_display",
        ]

    def validate(self, attrs):
        start = attrs.get(
            "discount_range_from",
            getattr(self.instance, "discount_range_from", None),
        )
        end = attrs.get("discount_range_to", getattr(self.instance, "discount_range_to", None))
        if start is None or end is None or end <= start:
            raise serializers.ValidationError(
                {"discount_range_to": "Range end must be greater than range start."}
            )

        # Overlapping ranges would make routing ambiguous — §7.1 expects exactly one match.
        siblings = ApprovalChainRule.objects.filter(company=self.context["membership"].company)
        if self.instance:
            siblings = siblings.exclude(pk=self.instance.pk)
        clash = siblings.filter(
            discount_range_from__lt=end, discount_range_to__gt=start
        ).first()
        if clash:
            raise serializers.ValidationError(
                {
                    "discount_range_from": (
                        f"Overlaps the existing rule {clash.discount_range_from}–"
                        f"{clash.discount_range_to}."
                    )
                }
            )
        return attrs
