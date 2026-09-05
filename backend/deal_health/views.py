from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner
from deal_health.models import AnomalyAlert
from deal_health.serializers import AnomalyAlertSerializer, EscalateAlertRequestSerializer
from deal_health.services import escalate_alert, nudge_rep, run_deal_health_scan


class AnomalyAlertViewSet(viewsets.ModelViewSet):
    serializer_class = AnomalyAlertSerializer
    permission_classes = [IsCompanyMember]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return AnomalyAlert.objects.none()
        qs = AnomalyAlert.objects.filter(company=membership.company)
        qs = scope_to_owner(qs, membership, self.request.user, owner_field="quotation__owner")

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        severity_param = self.request.query_params.get("severity")
        if severity_param:
            qs = qs.filter(severity=severity_param)

        alert_type_param = self.request.query_params.get("alert_type")
        if alert_type_param:
            qs = qs.filter(alert_type=alert_type_param)

        return qs

    @action(detail=False, methods=["post"], url_path="scan")
    def trigger_scan(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Active membership required"}, status=status.HTTP_403_FORBIDDEN)
        res = run_deal_health_scan(membership.company)
        return Response(res, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="escalate")
    def escalate(self, request, pk=None):
        alert = self.get_object()
        ser = EscalateAlertRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updated = escalate_alert(alert, request.user, note=ser.validated_data.get("note", ""))
        return Response(AnomalyAlertSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="nudge")
    def nudge(self, request, pk=None):
        alert = self.get_object()
        updated = nudge_rep(alert, request.user)
        return Response(AnomalyAlertSerializer(updated).data)
