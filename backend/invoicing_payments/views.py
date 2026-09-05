from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Role
from accounts.permissions import IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner

from .models import Invoice
from .serializers import (
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    RecordPaymentSerializer,
)
from .services import invoice_summary_text, record_payment

# §3: Finance / Ops "reconcile billing/credit notes"; Admin has everything. Recording a
# payment moves money against a financial record, so it stops here — a rep can watch
# their own invoice get paid but cannot mark it paid.
FINANCE_ROLES = {Role.FINANCE_OPS, Role.ADMIN}


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Screens 12-13.

    §9 lists the invoice screens for Rep / Finance / Admin, so read access follows that
    set with a rep scoped to their own deals. Every *mutating* action is gated to Finance
    and Admin below.
    """

    permission_classes = [IsCompanyMember]
    lookup_value_regex = "[0-9a-f-]{36}"

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceDetailSerializer

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "membership": self.membership,
            "can_record_payment": self.membership.role.code in FINANCE_ROLES,
        }

    def get_queryset(self):
        qs = (
            Invoice.objects.filter(customer__company=self.membership.company)
            .select_related("customer", "quotation", "quotation__owner")
            .prefetch_related(
                "lines__product",
                "lines__subscription__product",
                "lines__subscription__plan",
                "lines__billing_cycle",
                "payments__recorded_by",
                "credit_notes__issued_by",
            )
        )
        # A rep follows their own deal into billing; every other role sees the company's
        # invoices (§12). Invoices raised outside a quotation (a pure recurring run) have
        # no owner, so they are Finance/Admin-visible only — which matches who is
        # responsible for them.
        qs = scope_to_owner(qs, self.membership, self.request.user, "quotation__owner")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        type_filter = self.request.query_params.get("type")
        if type_filter:
            qs = qs.filter(invoice_type=type_filter)
        customer = self.request.query_params.get("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        return qs

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        if self.membership.role.code not in FINANCE_ROLES:
            raise PermissionDenied("Only Finance / Ops or an Admin can record a payment.")
        invoice = self.get_object()
        if invoice.status == Invoice.VOID:
            raise ValidationError({"detail": "This invoice is void."})

        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["amount"] > invoice.balance_due:
            raise ValidationError(
                {
                    "amount": (
                        f"Exceeds the outstanding balance of {invoice.balance_due}. "
                        "Record the balance, or raise a credit note for the difference."
                    )
                }
            )

        record_payment(
            invoice,
            request.user,
            data["amount"],
            method=data["method"],
            reference=data.get("reference", ""),
        )
        invoice.refresh_from_db()
        return Response(
            InvoiceDetailSerializer(invoice, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["get"], url_path="download-summary")
    def download_summary(self, request, pk=None):
        """§8's download endpoint. Plain text rather than a rendered PDF — no PDF
        dependency is in the stack, and the point of the artefact here is that the
        one-time and recurring blocks are separated in the document itself."""
        invoice = self.get_object()
        response = HttpResponse(invoice_summary_text(invoice), content_type="text/plain")
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.invoice_number}.txt"'
        )
        return response
