from rest_framework import serializers

from .models import ApprovalRequest, ApprovalStep


class ApprovalStepSerializer(serializers.ModelSerializer):
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalStep
        fields = [
            "id",
            "stage",
            "stage_label",
            "sequence",
            "reviewer",
            "reviewer_name",
            "action",
            "reason",
            "acted_at",
        ]

    def get_reviewer_name(self, step):
        return (step.reviewer.full_name or step.reviewer.email) if step.reviewer else None


class ApprovalRequestSerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, read_only=True)
    quotation_number = serializers.CharField(source="quotation.number", read_only=True)
    customer_name = serializers.CharField(source="quotation.customer.name", read_only=True)
    owner_name = serializers.SerializerMethodField()
    current_stage = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    can_act = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "quotation",
            "quotation_number",
            "customer_name",
            "owner_name",
            "risk_score_snapshot",
            "required_level",
            "status",
            "current_stage",
            "total_value",
            "can_act",
            "steps",
            "created_at",
        ]

    def get_owner_name(self, request):
        owner = request.quotation.owner
        return owner.full_name or owner.email

    def get_current_stage(self, request):
        step = request.current_step
        return step.stage if step else None

    def get_total_value(self, request):
        return str(request.quotation.total_value)

    def get_can_act(self, approval_request):
        """Whether *this* viewer may act on the current step — the UI enables the
        Approve/Reject buttons off this, and the API re-checks it independently."""
        from .services import ROLE_FOR_STAGE

        membership = self.context.get("membership")
        user = getattr(self.context.get("request"), "user", None)
        step = approval_request.current_step
        if step is None or approval_request.status != ApprovalRequest.PENDING:
            return False
        if membership is None or membership.role.code != ROLE_FOR_STAGE[step.stage]:
            return False
        return approval_request.quotation.owner_id != getattr(user, "id", None)


class ApprovalActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
