from decimal import Decimal

from rest_framework import serializers

from .models import BillingCycle, ProrationEvent, Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    cycle_months = serializers.IntegerField(read_only=True)
    refund_type = serializers.CharField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "product",
            "product_name",
            "cycle",
            "cycle_months",
            "proration_rule",
            "cancellation_rule",
            "refund_type",
            "is_active",
        ]


class BillingCycleSerializer(serializers.ModelSerializer):
    is_billed = serializers.BooleanField(read_only=True)
    days_in_cycle = serializers.IntegerField(read_only=True)
    invoice_id = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    # The standard, un-prorated charge, so the schedule can flag a period whose amount
    # was moved off the norm by a proration event instead of silently showing an odd
    # number (Screen 10).
    standard_amount = serializers.SerializerMethodField()

    class Meta:
        model = BillingCycle
        fields = [
            "id",
            "period_start",
            "period_end",
            "amount",
            "standard_amount",
            "is_billed",
            "days_in_cycle",
            "invoice_id",
            "invoice_number",
        ]

    def get_invoice_id(self, cycle):
        return str(cycle.invoice_line.invoice_id) if cycle.invoice_line_id else None

    def get_invoice_number(self, cycle):
        return cycle.invoice_line.invoice.invoice_number if cycle.invoice_line_id else None

    def get_standard_amount(self, cycle):
        return str(cycle.subscription.cycle_amount)


class ProrationEventSerializer(serializers.ModelSerializer):
    change_type_label = serializers.CharField(source="get_change_type_display", read_only=True)

    class Meta:
        model = ProrationEvent
        fields = [
            "id",
            "change_type",
            "change_type_label",
            "delta_amount",
            "effective_date",
            "billing_cycle",
            "details",
            "created_at",
        ]


class SubscriptionListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_tier = serializers.CharField(source="customer.tier", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    cycle = serializers.CharField(source="plan.cycle", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    cycle_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    quotation_number = serializers.CharField(
        source="quotation.number", read_only=True, default=None
    )
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "customer",
            "customer_name",
            "customer_tier",
            "product",
            "product_name",
            "plan",
            "plan_name",
            "cycle",
            "qty",
            "unit_price",
            "cycle_amount",
            "status",
            "status_label",
            "start_date",
            "next_bill_date",
            "quotation",
            "quotation_number",
            "owner_name",
            "created_at",
        ]

    def get_owner_name(self, subscription):
        owner = subscription.quotation.owner if subscription.quotation_id else None
        return (owner.full_name or owner.email) if owner else None


class SubscriptionDetailSerializer(SubscriptionListSerializer):
    """Everything Screen 10 needs: the details card, the billing schedule timeline, the
    proration audit trail, and the one-time siblings from the same order so the split
    billing view can show what else was on the deal."""

    billing_cycles = serializers.SerializerMethodField()
    proration_events = ProrationEventSerializer(many=True, read_only=True)
    current_cycle = serializers.SerializerMethodField()
    plan_detail = SubscriptionPlanSerializer(source="plan", read_only=True)
    lifetime_billed = serializers.SerializerMethodField()
    scheduled_value = serializers.SerializerMethodField()
    order_one_time_lines = serializers.SerializerMethodField()
    credit_notes = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_refund = serializers.SerializerMethodField()

    class Meta(SubscriptionListSerializer.Meta):
        fields = SubscriptionListSerializer.Meta.fields + [
            "plan_detail",
            "billing_cycles",
            "current_cycle",
            "proration_events",
            "lifetime_billed",
            "scheduled_value",
            "order_one_time_lines",
            "credit_notes",
            "cancelled_at",
            "cancellation_reason",
            "paused_at",
            "can_manage",
            "can_refund",
        ]

    def get_billing_cycles(self, subscription):
        return BillingCycleSerializer(subscription.billing_cycles.all(), many=True).data

    def get_current_cycle(self, subscription):
        cycle = subscription.current_cycle
        return BillingCycleSerializer(cycle).data if cycle else None

    def get_lifetime_billed(self, subscription):
        return str(
            sum(
                (cycle.amount for cycle in subscription.billing_cycles.all() if cycle.is_billed),
                Decimal("0.00"),
            )
        )

    def get_scheduled_value(self, subscription):
        return str(
            sum(
                (
                    cycle.amount
                    for cycle in subscription.billing_cycles.all()
                    if not cycle.is_billed
                ),
                Decimal("0.00"),
            )
        )

    def get_order_one_time_lines(self, subscription):
        """The one-time products bought on the same order. Read from the order invoice's
        product-linked lines, never merged with the recurring ones — Screen 10's split
        billing view is showing two pools, not one list filtered twice."""
        if not subscription.quotation_id:
            return []
        invoice = subscription.quotation.invoices.filter(
            invoice_type="one_time"
        ).first()
        if invoice is None:
            return []
        return [
            {
                "id": str(line.id),
                "description": line.description,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "amount": str(line.amount),
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
            }
            for line in invoice.one_time_lines
        ]

    def get_credit_notes(self, subscription):
        return [
            {
                "id": str(note.id),
                "amount": str(note.amount),
                "reason": note.reason,
                "issued_at": note.issued_at,
                "invoice_id": str(note.invoice_id) if note.invoice_id else None,
                "invoice_number": note.invoice.invoice_number if note.invoice_id else None,
            }
            for note in subscription.credit_notes.all()
        ]

    def get_can_manage(self, subscription):
        return self.context.get("can_manage", False)

    def get_can_refund(self, subscription):
        return self.context.get("can_refund", False)


class ModifySubscriptionSerializer(serializers.Serializer):
    new_qty = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    new_plan = serializers.UUIDField(required=False)
    effective_date = serializers.DateField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if "new_qty" not in attrs and "new_plan" not in attrs:
            raise serializers.ValidationError("Provide new_qty and/or new_plan.")
        return attrs


class PauseSubscriptionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class CancelSubscriptionSerializer(serializers.Serializer):
    # Mandatory: a cancellation can move money via a credit note, and §12 requires a
    # reason on every action that does.
    reason = serializers.CharField(allow_blank=False)
    effective_date = serializers.DateField(required=False)


class BillingRunSerializer(serializers.Serializer):
    # Lets a demo bill a future period without waiting for the calendar.
    as_of = serializers.DateField(required=False)
