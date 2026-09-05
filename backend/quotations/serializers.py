from decimal import Decimal

from rest_framework import serializers

from accounts.models import Customer
from catalog.models import Product, ProductVariant

from .models import Quotation, QuotationLine, QuotationStatusHistory


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "tier", "email", "location"]


class QuotationLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_category = serializers.CharField(source="product.category", read_only=True)
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model = QuotationLine
        fields = [
            "id",
            "product",
            "product_name",
            "product_category",
            "variant",
            "variant_label",
            "qty",
            "unit_price",
            "discount_pct",
            "line_total",
            "line_type",
        ]
        read_only_fields = ["line_total"]
        extra_kwargs = {"unit_price": {"required": False}}

    def get_variant_label(self, line):
        return f"{line.variant.attribute}: {line.variant.value}" if line.variant else None

    def validate_product(self, value):
        if value.company_id != self.context["membership"].company_id:
            raise serializers.ValidationError("Product belongs to another company.")
        return value

    def validate(self, attrs):
        product = attrs.get("product") or getattr(self.instance, "product", None)
        variant = attrs.get("variant", getattr(self.instance, "variant", None))
        if variant and product and variant.product_id != product.id:
            raise serializers.ValidationError({"variant": "Variant does not belong to this product."})

        # Price is snapshotted from the catalog at add-time unless one is passed in.
        if not self.instance and attrs.get("unit_price") is None:
            base = product.base_price + (variant.extra_price if variant else Decimal("0.00"))
            attrs["unit_price"] = base
        if product and not attrs.get("line_type"):
            attrs["line_type"] = (
                QuotationLine.RECURRING if product.is_subscription else QuotationLine.ONE_TIME
            )
        return attrs


class QuotationStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = QuotationStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by_name", "changed_at"]

    def get_changed_by_name(self, history):
        user = history.changed_by
        return (user.full_name or user.email) if user else "System"


class QuotationListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_tier = serializers.CharField(source="customer.tier", read_only=True)
    owner_name = serializers.SerializerMethodField()
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_count = serializers.IntegerField(source="lines.count", read_only=True)
    routing_score = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = Quotation
        fields = [
            "id",
            "number",
            "status",
            "customer",
            "customer_name",
            "customer_tier",
            "owner",
            "owner_name",
            "blended_risk_score",
            "max_single_overage",
            "routing_score",
            "total_value",
            "line_count",
            "valid_till",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "owner",
            "blended_risk_score",
            "max_single_overage",
        ]

    def get_owner_name(self, quotation):
        return quotation.owner.full_name or quotation.owner.email

    def validate_customer(self, value):
        if value.company_id != self.context["membership"].company_id:
            raise serializers.ValidationError("Customer belongs to another company.")
        return value


class QuotationDetailSerializer(QuotationListSerializer):
    customer_detail = CustomerSerializer(source="customer", read_only=True)
    lines = QuotationLineSerializer(many=True, read_only=True)
    status_history = QuotationStatusHistorySerializer(many=True, read_only=True)
    average_discount_pct = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )
    can_edit = serializers.SerializerMethodField()
    active_approval = serializers.SerializerMethodField()
    last_decision = serializers.SerializerMethodField()

    class Meta(QuotationListSerializer.Meta):
        fields = QuotationListSerializer.Meta.fields + [
            "customer_detail",
            "lines",
            "status_history",
            "average_discount_pct",
            "can_edit",
            "active_approval",
            "last_decision",
        ]

    def get_can_edit(self, quotation):
        return quotation.status in Quotation.EDITABLE_STATUSES

    def get_active_approval(self, quotation):
        """The cycle currently in flight, so the quote page can link straight to it
        instead of leaving the rep guessing who is sitting on the deal."""
        from approvals.models import ApprovalRequest

        request = quotation.approval_requests.filter(status=ApprovalRequest.PENDING).first()
        if request is None:
            return None
        step = request.current_step
        return {
            "id": str(request.id),
            "required_level": request.required_level,
            "risk_score_snapshot": str(request.risk_score_snapshot),
            "current_stage": step.stage if step else None,
            "current_stage_label": step.get_stage_display() if step else None,
        }

    def get_last_decision(self, quotation):
        """The most recent reviewer action — this is how a returned or rejected quote
        finally shows the rep *why* it came back."""
        from approvals.models import ApprovalStep

        step = (
            ApprovalStep.objects.filter(approval_request__quotation=quotation)
            .exclude(action=ApprovalStep.PENDING)
            .select_related("reviewer")
            .order_by("-acted_at")
            .first()
        )
        if step is None:
            return None
        return {
            "action": step.action,
            "stage_label": step.get_stage_display(),
            "reason": step.reason,
            "reviewer_name": (
                (step.reviewer.full_name or step.reviewer.email) if step.reviewer else None
            ),
            "acted_at": step.acted_at,
        }
