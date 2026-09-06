from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from accounts.permissions import IsAdminOrReadOnly, IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner

from .models import Subscription, SubscriptionPlan
from .serializers import (
    BillingRunSerializer,
    CancelSubscriptionSerializer,
    ModifySubscriptionSerializer,
    PauseSubscriptionSerializer,
    SubscriptionDetailSerializer,
    SubscriptionListSerializer,
    SubscriptionPlanSerializer,
)
from .services import (
    cancel_subscription,
    modify_subscription,
    pause_subscription,
    resume_subscription,
    run_recurring_billing,
)

# A mid-cycle quantity change is ordinary account management, so the rep who owns the
# deal can make one on their own subscription (queryset scoping already limits which
# rows that is).
MANAGE_ROLES = {Role.SALES_REP, Role.SALES_MANAGER, Role.FINANCE_OPS, Role.ADMIN}
# Cancellation issues a credit note, i.e. it moves money. §3 gives "reconcile
# billing/credit notes" to Finance / Ops, and everything to Admin — nobody else.
REFUND_ROLES = {Role.FINANCE_OPS, Role.ADMIN}


class MembershipScopedViewSet(viewsets.GenericViewSet):
    permission_classes = [IsCompanyMember]
    lookup_value_regex = "[0-9a-f-]{36}"

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    @property
    def role_code(self):
        return self.membership.role.code

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "membership": self.membership,
            "can_manage": self.role_code in MANAGE_ROLES,
            "can_refund": self.role_code in REFUND_ROLES,
        }


def subscription_queryset(membership, user):
    """Company-scoped, then owner-scoped per §12.

    A rep is scoped through `quotation__owner`. If the originating quotation is ever
    deleted the link goes null by design (§5.8) and the subscription drops out of a rep's
    list — the conservative direction, since Finance and Admin still see every row.
    """
    qs = (
        Subscription.objects.filter(customer__company=membership.company)
        .select_related("customer", "product", "plan", "quotation", "quotation__owner")
        .prefetch_related(
            "billing_cycles__invoice_line__invoice",
            "proration_events",
            "credit_notes__invoice",
        )
    )
    return scope_to_owner(qs, membership, user, "quotation__owner")


class SubscriptionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, MembershipScopedViewSet
):
    """Screen 9 — visible to Rep (own), Manager, Finance and Admin per §9."""

    def get_serializer_class(self):
        return (
            SubscriptionListSerializer
            if self.action == "list"
            else SubscriptionDetailSerializer
        )

    def get_queryset(self):
        qs = subscription_queryset(self.membership, self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        customer = self.request.query_params.get("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        return qs

    def detail_response(self, subscription):
        subscription.refresh_from_db()
        return Response(
            SubscriptionDetailSerializer(
                subscription, context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def modify(self, request, pk=None):
        if self.role_code not in MANAGE_ROLES:
            raise PermissionDenied("Your role cannot modify a subscription.")
        subscription = self.get_object()
        serializer = ModifySubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_plan = None
        if data.get("new_plan"):
            new_plan = SubscriptionPlan.objects.filter(
                id=data["new_plan"], company=self.membership.company
            ).first()
            if new_plan is None:
                raise ValidationError({"new_plan": "Unknown plan for this company."})

        try:
            modify_subscription(
                subscription,
                request.user,
                new_qty=data.get("new_qty"),
                new_plan=new_plan,
                effective_date=data.get("effective_date"),
                reason=data.get("reason", ""),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        return self.detail_response(subscription)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        # A hold on billing, not a refund — same MANAGE_ROLES gate as `modify`.
        if self.role_code not in MANAGE_ROLES:
            raise PermissionDenied("Your role cannot pause a subscription.")
        subscription = self.get_object()
        serializer = PauseSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pause_subscription(
                subscription, request.user, reason=serializer.validated_data.get("reason", "")
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        return self.detail_response(subscription)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        if self.role_code not in MANAGE_ROLES:
            raise PermissionDenied("Your role cannot resume a subscription.")
        subscription = self.get_object()
        serializer = PauseSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resume_subscription(
                subscription, request.user, reason=serializer.validated_data.get("reason", "")
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        return self.detail_response(subscription)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if self.role_code not in REFUND_ROLES:
            raise PermissionDenied(
                "Cancelling a subscription issues a credit note — Finance / Ops or Admin only."
            )
        subscription = self.get_object()
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cancel_subscription(
                subscription,
                request.user,
                reason=serializer.validated_data["reason"],
                effective_date=serializer.validated_data.get("effective_date"),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})
        return self.detail_response(subscription)


class BillingDetailView(APIView):
    """`GET /api/billing/{id}` per §8 — the billing schedule for one subscription
    (Screen 10). Same payload as the subscription detail; §8 names it separately because
    the route is what the billing screen links to."""

    permission_classes = [IsCompanyMember]

    def get(self, request, pk):
        membership = get_membership(request)
        subscription = subscription_queryset(membership, request.user).filter(pk=pk).first()
        if subscription is None:
            raise PermissionDenied("No such subscription for this user.")
        context = {
            "request": request,
            "membership": membership,
            "can_manage": membership.role.code in MANAGE_ROLES,
            "can_refund": membership.role.code in REFUND_ROLES,
        }
        return Response(SubscriptionDetailSerializer(subscription, context=context).data)


class BillingRunView(APIView):
    """Manual trigger for the recurring billing run (§7.3.4).

    Celery/Redis are not wired into this build yet, so the Beat job is exposed as an
    endpoint — the same pattern the replenishment watcher uses. The service function it
    calls is already the task body.
    """

    permission_classes = [IsCompanyMember]

    def post(self, request):
        membership = get_membership(request)
        if membership.role.code not in REFUND_ROLES:
            raise PermissionDenied("Only Finance / Ops or an Admin can run recurring billing.")

        serializer = BillingRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = run_recurring_billing(
            company=membership.company,
            as_of=serializer.validated_data.get("as_of"),
            actor=request.user,
        )
        return Response(
            {
                "as_of": result["as_of"],
                "invoices_created": len(result["invoices"]),
                "invoices": [
                    {
                        "id": str(invoice.id),
                        "invoice_number": invoice.invoice_number,
                        "customer": invoice.customer.name,
                        "total_amount": str(invoice.total_amount),
                        "recurring_lines": len(invoice.recurring_lines),
                        "one_time_lines": len(invoice.one_time_lines),
                    }
                    for invoice in result["invoices"]
                ],
            }
        )


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """§8 Subscription Plan Config. Any member may read (the modify dialog needs the plan
    list); only Admin may write, per §12's config-screen rule."""

    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_queryset(self):
        membership = get_membership(self.request)
        if membership is None:
            return SubscriptionPlan.objects.none()
        return SubscriptionPlan.objects.filter(company=membership.company).select_related(
            "product"
        )

    def perform_create(self, serializer):
        serializer.save(company=get_membership(self.request).company)
