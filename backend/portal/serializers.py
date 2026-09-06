from decimal import Decimal

from rest_framework import serializers

from quotations.models import Quotation, QuotationLine

from .models import NegotiationMessage, PortalSession


class NegotiationMessageSerializer(serializers.ModelSerializer):
    """One thread entry, rendered identically on both sides of the auth boundary.

    `author_side` rather than raw ids: the portal must never learn an internal user's
    email or primary key just because that person posted in the thread.
    """

    author_side = serializers.CharField(read_only=True)
    author_name = serializers.CharField(read_only=True)
    line_label = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationMessage
        fields = [
            "id",
            "message_type",
            "body",
            "counter_discount_pct",
            "requested_delivery_date",
            "author_side",
            "author_name",
            "quotation_line",
            "line_label",
            "created_at",
        ]

    def get_line_label(self, message):
        return message.quotation_line.product.name if message.quotation_line_id else None


class PortalQuotationLineSerializer(serializers.ModelSerializer):
    """Deliberately narrower than the internal line serializer: no internal ids beyond the
    line's own, and nothing about ceilings, overage or routing scores. The customer sees
    the terms of their deal, never the governance rules those terms are measured against.
    """

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_category = serializers.CharField(source="product.category", read_only=True)
    variant_label = serializers.SerializerMethodField()
    list_total = serializers.SerializerMethodField()

    class Meta:
        model = QuotationLine
        fields = [
            "id",
            "product_name",
            "product_category",
            "variant_label",
            "qty",
            "unit_price",
            "discount_pct",
            "list_total",
            "line_total",
            "line_type",
        ]

    def get_variant_label(self, line):
        return f"{line.variant.attribute}: {line.variant.value}" if line.variant else None

    def get_list_total(self, line):
        return (line.qty * line.unit_price).quantize(Decimal("0.01"))


class PortalQuotationSerializer(serializers.ModelSerializer):
    """The whole portal payload: quote header, lines, thread, and what the customer may
    do next. `can_act` is computed server-side so the buttons a portal renders are never
    the source of truth for what the API will accept."""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_tier = serializers.CharField(source="customer.tier", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_location = serializers.CharField(source="customer.location", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    owner_name = serializers.SerializerMethodField()
    lines = PortalQuotationLineSerializer(many=True, read_only=True)
    messages = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    can_act = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Quotation
        fields = [
            "id",
            "number",
            "status",
            "status_label",
            "company_name",
            "customer_name",
            "customer_tier",
            "customer_email",
            "customer_location",
            "owner_name",
            "valid_till",
            "created_at",
            "updated_at",
            "lines",
            "messages",
            "totals",
            "can_act",
        ]

    def get_owner_name(self, quotation):
        # Name only — the customer gets a person to talk about, not a login.
        return quotation.owner.full_name or "Your account manager"

    def get_messages(self, quotation):
        return NegotiationMessageSerializer(
            quotation.negotiation_messages.select_related(
                "author_user", "author_customer", "quotation_line__product"
            ),
            many=True,
        ).data

    def get_totals(self, quotation):
        lines = list(quotation.lines.all())
        gross = sum((line.qty * line.unit_price for line in lines), Decimal("0.00"))
        net = sum((line.line_total for line in lines), Decimal("0.00"))
        return {
            "gross": str(gross.quantize(Decimal("0.01"))),
            "discount": str((gross - net).quantize(Decimal("0.01"))),
            "net": str(net.quantize(Decimal("0.01"))),
            "average_discount_pct": str(quotation.average_discount_pct),
        }

    def get_can_act(self, quotation):
        from .services import ACTIONABLE_STATUSES

        return quotation.status in ACTIONABLE_STATUSES


class PortalSessionSerializer(serializers.ModelSerializer):
    """The link's own metadata. Note the absence of `token_hash` — nothing about the
    credential itself is ever serialised back out."""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    quotation_number = serializers.CharField(source="quotation.number", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = PortalSession
        fields = [
            "id",
            "quotation",
            "quotation_number",
            "customer",
            "customer_name",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "is_active",
            "created_at",
        ]


class CommentInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)
    quotation_line = serializers.UUIDField(required=False, allow_null=True)
    # Optional echo of the quotation the client believes it is acting on. Never used to
    # look anything up — only to be compared against the token's own scope.
    quotation = serializers.UUIDField(required=False, allow_null=True)


class CounterOfferInputSerializer(CommentInputSerializer):
    body = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, trim_whitespace=True, default=""
    )
    counter_discount_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100")
    )


class DeliveryDateInputSerializer(serializers.Serializer):
    requested_delivery_date = serializers.DateField()
    body = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, trim_whitespace=True, default=""
    )
    quotation_line = serializers.UUIDField(required=False, allow_null=True)
    quotation = serializers.UUIDField(required=False, allow_null=True)


class ConfirmInputSerializer(serializers.Serializer):
    body = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, trim_whitespace=True, default=""
    )
    quotation = serializers.UUIDField(required=False, allow_null=True)


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class CustomerQuotationSummarySerializer(serializers.ModelSerializer):
    """One row of the "My Quotations" list — deliberately narrower than the internal
    list serializer: a status and a total is enough to decide what to open next, nothing
    about risk scores or governance internals (§5.9)."""

    total_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Quotation
        fields = ["id", "number", "status", "company_name", "total_value", "valid_till", "updated_at"]
