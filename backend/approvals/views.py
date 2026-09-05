from django.contrib.contenttypes.models import ContentType
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner
from audit_log.models import AuditEntry
from quotations.models import Quotation
from quotations.serializers import QuotationDetailSerializer

from .models import ApprovalRequest, ApprovalStep
from .serializers import ApprovalActionSerializer, ApprovalRequestSerializer
from .services import act_on_request


class ApprovalViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsCompanyMember]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}

    def get_queryset(self):
        qs = (
            ApprovalRequest.objects.filter(quotation__company=self.membership.company)
            .select_related("quotation", "quotation__customer", "quotation__owner")
            .prefetch_related("steps__reviewer", "quotation__lines")
        )
        # A rep can watch their own deal move through review, but never anyone else's.
        qs = scope_to_owner(qs, self.membership, self.request.user, "quotation__owner")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        return qs

    def retrieve(self, request, *args, **kwargs):
        approval_request = self.get_object()
        quotation = approval_request.quotation
        audit = AuditEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Quotation), object_id=quotation.id
        ).select_related("user")[:50]
        return Response(
            {
                **self.get_serializer(approval_request).data,
                "quotation_detail": QuotationDetailSerializer(
                    quotation, context=self.get_serializer_context()
                ).data,
                "audit": [
                    {
                        "id": str(entry.id),
                        "action": entry.action,
                        "reason": entry.reason,
                        "user": (entry.user.full_name or entry.user.email) if entry.user else "System",
                        "created_at": entry.created_at,
                        "metadata": entry.metadata,
                    }
                    for entry in audit
                ],
            }
        )

    def _act(self, request, pk, action_value):
        approval_request = self.get_object()
        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act_on_request(
            approval_request,
            request.user,
            self.membership,
            action_value,
            serializer.validated_data.get("reason", ""),
        )
        approval_request.refresh_from_db()
        return Response(self.get_serializer(approval_request).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._act(request, pk, ApprovalStep.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._act(request, pk, ApprovalStep.REJECTED)

    @action(detail=True, methods=["post"], url_path="return")
    def return_to_rep(self, request, pk=None):
        return self._act(request, pk, ApprovalStep.RETURNED)
