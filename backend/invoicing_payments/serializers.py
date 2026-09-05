from decimal import Decimal

from rest_framework import serializers

from .models import CreditNote, Invoice, InvoiceLine, Payment


class InvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    subscription_product = serializers.CharField(
        source="subscription.product.name", read_only=True, default=None
    )
    plan_name = serializers.CharField(source="subscription.plan.name", read_only=True, default=None)
    cycle = serializers.CharField(source="subscription.plan.cycle", read_only=True, default=None)
    period_start = serializers.SerializerMethodField()
    period_end = serializers.SerializerMethodField()
    # Explicit rather than inferred from which FK is populated, so a consumer never has
    # to re-derive the one-time / recurring split itself.
    kind = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "kind",
            "description",
            "qty",
            "unit_price",
            "amount",
            "product",
            "product_name",
            "subscription",
            "subscription_product",
            "plan_name",
            "cycle",
            "period_start",
            "period_end",
        ]

    def get_kind(self, line):
        return "recurring" if line.is_recurring else "one_time"

    def _cycle(self, line):
        return getattr(line, "billing_cycle", None)

    def get_period_start(self, line):
        cycle = self._cycle(line)
        return cycle.period_start if cycle else None

    def get_period_end(self, line):
        cycle = self._cycle(line)
        return cycle.period_end if cycle else None


class PaymentSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "method",
            "method_label",
            "paid_at",
            "reference",
            "recorded_by_name",
        ]

    def get_recorded_by_name(self, payment):
        user = payment.recorded_by
        return (user.full_name or user.email) if user else None


class CreditNoteSerializer(serializers.ModelSerializer):
    issued_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CreditNote
        fields = ["id", "amount", "reason", "issued_at", "subscription", "issued_by_name"]

    def get_issued_by_name(self, note):
        user = note.issued_by
        return (user.full_name or user.email) if user else None


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_tier = serializers.CharField(source="customer.tier", read_only=True)
    quotation_number = serializers.CharField(
        source="quotation.number", read_only=True, default=None
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    type_label = serializers.CharField(source="get_invoice_type_display", read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    one_time_subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    recurring_subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    has_one_time = serializers.BooleanField(read_only=True)
    has_recurring = serializers.BooleanField(read_only=True)
    is_mixed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "invoice_type",
            "type_label",
            "customer",
            "customer_name",
            "customer_tier",
            "quotation",
            "quotation_number",
            "status",
            "status_label",
            "issue_date",
            "due_date",
            "total_amount",
            "amount_paid",
            "balance_due",
            "one_time_subtotal",
            "recurring_subtotal",
            "has_one_time",
            "has_recurring",
            "is_mixed",
        ]


class InvoiceDetailSerializer(InvoiceListSerializer):
    """Screen 13.

    `one_time_lines` and `recurring_lines` are served as two arrays, and there is no
    combined `lines` field at all. The API shape is what makes the structural separation
    impossible to lose in the UI: there is nothing for a client to accidentally render as
    one table.
    """

    one_time_lines = serializers.SerializerMethodField()
    recurring_lines = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)
    credit_notes = CreditNoteSerializer(many=True, read_only=True)
    amount_credited = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    owner_name = serializers.SerializerMethodField()
    can_record_payment = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "one_time_lines",
            "recurring_lines",
            "payments",
            "credit_notes",
            "amount_credited",
            "owner_name",
            "can_record_payment",
            "created_at",
        ]

    def get_one_time_lines(self, invoice):
        return InvoiceLineSerializer(invoice.one_time_lines, many=True).data

    def get_recurring_lines(self, invoice):
        return InvoiceLineSerializer(invoice.recurring_lines, many=True).data

    def get_owner_name(self, invoice):
        owner = invoice.quotation.owner if invoice.quotation_id else None
        return (owner.full_name or owner.email) if owner else None

    def get_can_record_payment(self, invoice):
        return self.context.get("can_record_payment", False)


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    method = serializers.ChoiceField(
        choices=[choice[0] for choice in Payment.METHOD_CHOICES], default=Payment.BANK_TRANSFER
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="")
