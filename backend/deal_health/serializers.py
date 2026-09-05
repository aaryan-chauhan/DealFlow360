from rest_framework import serializers
from deal_health.models import AnomalyAlert


class AnomalyAlertSerializer(serializers.ModelSerializer):
    quotation_number = serializers.CharField(source="quotation.number", read_only=True, default=None)
    customer_name = serializers.CharField(source="quotation.customer.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="quotation.owner.full_name", read_only=True, default=None)
    total_amount = serializers.DecimalField(source="quotation.total_value", max_digits=12, decimal_places=2, read_only=True, default=None)

    class Meta:
        model = AnomalyAlert
        fields = [
            "id",
            "alert_type",
            "severity",
            "status",
            "title",
            "description",
            "recommended_action",
            "quotation",
            "quotation_number",
            "customer_name",
            "owner_name",
            "total_amount",
            "nudge_count",
            "last_nudged_at",
            "escalated_at",
            "escalated_by_name",
            "escalation_note",
            "created_at",
            "updated_at",
        ]


class EscalateAlertRequestSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")
