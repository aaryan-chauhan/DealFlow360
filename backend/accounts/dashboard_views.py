from decimal import Decimal
from django.db import models
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from approvals.models import ApprovalRequest, ApprovalStep
from invoicing_payments.models import Invoice
from quotations.models import Quotation
from subscriptions_billing.models import Subscription
from warehouses_fulfillment.models import FulfillmentOrder

from .permissions import IsCompanyMember
from .scoping import get_membership, scope_to_owner

ZERO = Decimal("0.00")


class DashboardSummaryView(APIView):
    """Returns aggregated pipeline, revenue, approval, and fulfillment metrics for the workspace (spec §8)."""

    permission_classes = [IsCompanyMember]

    def get(self, request):
        membership = get_membership(request)
        if membership is None:
            raise PermissionDenied("No active company membership.")

        company = membership.company
        user = request.user
        role_code = membership.role.code

        # Quotation pipeline metrics
        quotations_qs = Quotation.objects.filter(company=company).select_related("customer", "owner")
        scoped_quotations = scope_to_owner(quotations_qs, membership, user)

        status_counts = {}
        for code, label in Quotation.STATUS_CHOICES:
            status_counts[code] = 0

        status_data = scoped_quotations.values("status").annotate(
            count=models.Count("id"),
        )
        for entry in status_data:
            status_counts[entry["status"]] = entry["count"]

        total_pipeline_value = sum(
            (q.total_value for q in scoped_quotations.filter(status__in=[Quotation.APPROVED, Quotation.NEGOTIATION, Quotation.PENDING_APPROVAL, Quotation.CONFIRMED])),
            ZERO,
        )

        # Pending approvals count relevant to user
        pending_approvals_count = 0
        pending_approval_requests = []
        if role_code in ["sales_manager", "finance_ops", "admin"]:
            approval_qs = ApprovalRequest.objects.filter(
                quotation__company=company,
                status=ApprovalRequest.PENDING,
            ).select_related("quotation", "quotation__customer", "quotation__owner")

            for req in approval_qs:
                step = req.current_step
                if step:
                    stage_match = (
                        (step.stage == ApprovalStep.MANAGER and role_code in ["sales_manager", "admin"])
                        or (step.stage == ApprovalStep.FINANCE and role_code in ["finance_ops", "admin"])
                    )
                    if stage_match and req.quotation.owner_id != user.id:
                        pending_approvals_count += 1
                        pending_approval_requests.append({
                            "id": str(req.id),
                            "quotation_number": req.quotation.number,
                            "customer_name": req.quotation.customer.name,
                            "risk_score_snapshot": str(req.risk_score_snapshot),
                            "required_level": req.required_level,
                            "current_stage": step.get_stage_display(),
                            "created_at": req.created_at.isoformat(),
                        })

        # Subscriptions & MRR
        subs_qs = Subscription.objects.filter(customer__company=company, status=Subscription.ACTIVE)
        active_subscriptions_count = subs_qs.count()
        mrr = sum((sub.cycle_amount for sub in subs_qs), ZERO)

        # Fulfillment breakdown
        fulfillment_qs = FulfillmentOrder.objects.filter(quotation__company=company)
        fulfillment_counts = {
            "suggested": fulfillment_qs.filter(status=FulfillmentOrder.SUGGESTED).count(),
            "accepted": fulfillment_qs.filter(status=FulfillmentOrder.ACCEPTED).count(),
            "backordered": fulfillment_qs.filter(status=FulfillmentOrder.BACKORDERED).count(),
            "fulfilled": fulfillment_qs.filter(status=FulfillmentOrder.FULFILLED).count(),
        }

        # Invoicing totals
        invoices_qs = Invoice.objects.filter(customer__company=company)
        total_invoiced = sum((inv.total_amount for inv in invoices_qs), ZERO)
        total_paid = sum((inv.amount_paid for inv in invoices_qs), ZERO)
        balance_due = sum((inv.balance_due for inv in invoices_qs), ZERO)

        # Recent quotations (last 5)
        recent_quotes = [
            {
                "id": str(q.id),
                "number": q.number,
                "customer_name": q.customer.name,
                "status": q.status,
                "status_display": q.get_status_display(),
                "total_value": str(q.total_value),
                "routing_score": str(q.routing_score),
                "created_at": q.created_at.isoformat(),
            }
            for q in scoped_quotations[:5]
        ]

        return Response({
            "pipeline": {
                "total_value": str(total_pipeline_value),
                "total_count": scoped_quotations.count(),
                "by_status": status_counts,
            },
            "approvals": {
                "pending_count": pending_approvals_count,
                "pending_requests": pending_approval_requests[:5],
            },
            "subscriptions": {
                "active_count": active_subscriptions_count,
                "mrr": str(mrr),
            },
            "fulfillment": fulfillment_counts,
            "invoicing": {
                "total_invoiced": str(total_invoiced),
                "total_paid": str(total_paid),
                "balance_due": str(balance_due),
                "invoice_count": invoices_qs.count(),
            },
            "recent_quotations": recent_quotes,
        })
