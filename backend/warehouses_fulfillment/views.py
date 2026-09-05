from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from accounts.permissions import IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner

from .models import FulfillmentOrder
from .serializers import (
    ConsolidateSerializer,
    FulfillmentOrderDetailSerializer,
    FulfillmentOrderListSerializer,
    NotifySerializer,
    OverrideSerializer,
    StockLevelSerializer,
    WarehouseSerializer,
)

from .services import (
    accept_split,
    consolidate_backorder,
    notify_backorder_customer,
    override_split,
    scan_backorder_replenishment,
)

# Screen 8 (split table, override, backorder actions) is Finance / Admin per §9. Managers
# and reps can watch the plan but never move stock.
MANAGE_ROLES = {Role.FINANCE_OPS, Role.ADMIN}


class FulfillmentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsCompanyMember]
    # Pinned to a UUID so /api/fulfillment/orders and /api/fulfillment/scan-replenishment
    # can never be swallowed by the detail route (§8 puts all three under one prefix).
    lookup_value_regex = "[0-9a-f-]{36}"

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}

    def get_serializer_class(self):
        return (
            FulfillmentOrderListSerializer
            if self.action == "list"
            else FulfillmentOrderDetailSerializer
        )

    def get_queryset(self):
        qs = (
            FulfillmentOrder.objects.filter(quotation__company=self.membership.company)
            .select_related("quotation", "quotation__customer", "quotation__owner")
            .prefetch_related(
                "split_lines__warehouse",
                "split_lines__product",
                "backorder_events",
                "quotation__lines__product",
            )
        )
        # A rep can follow their own deal into fulfillment, never anyone else's; every
        # other role sees the whole company's orders (§12).
        qs = scope_to_owner(qs, self.membership, self.request.user, "quotation__owner")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        if self.request.query_params.get("backordered") == "true":
            qs = qs.filter(split_lines__is_backorder=True).distinct()
        return qs

    def assert_can_manage(self):
        if self.membership.role.code not in MANAGE_ROLES:
            raise PermissionDenied(
                "Only Finance / Ops or an Admin can change a warehouse split."
            )

    def detail_response(self, order):
        order.refresh_from_db()
        return Response(
            FulfillmentOrderDetailSerializer(
                order, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"], url_path="accept-split")
    def accept_split(self, request, pk=None):
        self.assert_can_manage()
        order = self.get_object()
        accept_split(order, request.user)
        return self.detail_response(order)

    @action(detail=True, methods=["post"])
    def override(self, request, pk=None):
        self.assert_can_manage()
        order = self.get_object()
        serializer = OverrideSerializer(
            data=request.data,
            context={**self.get_serializer_context(), "company": self.membership.company},
        )
        serializer.is_valid(raise_exception=True)
        override_split(
            order,
            request.user,
            serializer.validated_data["lines"],
            serializer.validated_data.get("reason", ""),
        )
        return self.detail_response(order)

    @action(detail=True, methods=["post"], url_path="consolidate-backorder")
    def consolidate_backorder(self, request, pk=None):
        self.assert_can_manage()
        order = self.get_object()
        serializer = ConsolidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consolidate_backorder(order, request.user, serializer.validated_data.get("line_ids"))
        return self.detail_response(order)

    @action(detail=True, methods=["post"], url_path="notify-customer")
    def notify_customer(self, request, pk=None):
        self.assert_can_manage()
        order = self.get_object()
        serializer = NotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notify_backorder_customer(order, request.user, serializer.validated_data.get("note", ""))
        return self.detail_response(order)


class ReplenishmentScanView(APIView):
    """Manual trigger for the backorder-consolidation watcher (§7.2.6).

    Celery/Redis are not wired into this build yet, so the scheduled Beat job is exposed
    as an admin-triggerable endpoint instead. It only *flags* lines whose stock has caught
    up — the operator still has to accept or override the consolidation.
    """

    permission_classes = [IsCompanyMember]

    def post(self, request):
        membership = get_membership(request)
        if membership.role.code not in MANAGE_ROLES:
            raise PermissionDenied("Only Finance / Ops or an Admin can run the stock scan.")

        result = scan_backorder_replenishment(company=membership.company)
        return Response(
            {
                "flagged": [
                    {
                        "fulfillment_order": str(line.fulfillment_order_id),
                        "quotation_number": line.fulfillment_order.quotation.number,
                        "product": line.product.name,
                        "warehouse": line.warehouse.name,
                        "qty": str(line.qty_fulfilled),
                    }
                    for line in result["flagged"]
                ],
                "cleared": [
                    {
                        "fulfillment_order": str(line.fulfillment_order_id),
                        "product": line.product.name,
                        "warehouse": line.warehouse.name,
                    }
                    for line in result["cleared"]
                ],
            }
        )


class WarehouseAdminViewSet(viewsets.ModelViewSet):
    """Admin CRUD for warehouses."""

    permission_classes = [IsCompanyMember]
    serializer_class = WarehouseSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership.")
        return membership

    def get_queryset(self):
        return Warehouse.objects.filter(company=self.membership.company)

    def perform_create(self, serializer):
        if self.membership.role.code not in MANAGE_ROLES:
            raise PermissionDenied("Only Admin or Finance can manage warehouses.")
        serializer.save(company=self.membership.company)

    def perform_update(self, serializer):
        if self.membership.role.code not in MANAGE_ROLES:
            raise PermissionDenied("Only Admin or Finance can update warehouses.")
        serializer.save()


class StockLevelAdminViewSet(viewsets.ModelViewSet):
    """Admin endpoint to view and adjust stock levels."""

    permission_classes = [IsCompanyMember]
    serializer_class = StockLevelSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership.")
        return membership

    def get_queryset(self):
        qs = StockLevel.objects.filter(warehouse__company=self.membership.company).select_related("warehouse", "product")
        warehouse_id = self.request.query_params.get("warehouse")
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    def perform_update(self, serializer):
        if self.membership.role.code not in MANAGE_ROLES:
            raise PermissionDenied("Only Admin or Finance can update stock levels.")
        serializer.save()

