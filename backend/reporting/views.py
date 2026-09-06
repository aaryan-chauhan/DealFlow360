from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSalesManager
from accounts.scoping import get_membership
from reporting.services import generate_reporting_pdf, generate_reporting_xlsx, get_reporting_summary


def _filters_from_params(params):
    return {
        "sales_rep_id": params.get("sales_rep") or None,
        "period": params.get("period") or params.get("date_range") or None,
        "date_from": params.get("date_from") or None,
        "date_to": params.get("date_to") or None,
        "approval_status": params.get("approval_status") or None,
        "category": params.get("category") or None,
        "product_id": params.get("product") or None,
    }


class ReportingSummaryView(APIView):
    permission_classes = [IsSalesManager]

    def get(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Active membership required"}, status=status.HTTP_403_FORBIDDEN)

        data = get_reporting_summary(membership.company, **_filters_from_params(request.query_params))
        return Response(data, status=status.HTTP_200_OK)


class ReportingExportView(APIView):
    """`GET /api/reports/export?format=pdf|xls` (spec §8).

    `format` here is this endpoint's own export-type parameter, not DRF's renderer-suffix
    query param of the same name — without this override, DRF's content negotiation reads
    it first and 404s because no renderer declares format='pdf'/'xls'.
    """

    permission_classes = [IsSalesManager]

    def perform_content_negotiation(self, request, force=False):
        # DRF's negotiation falls back to this same `?format=` query param to pick a
        # *renderer* (json/api) regardless of `format_kwarg` — since neither renderer
        # declares format='pdf'/'xls', that raises Http404 before `.get()` ever runs.
        # This view builds its own HttpResponse manually, so renderer negotiation is
        # irrelevant here; skip it.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Active membership required"}, status=status.HTTP_403_FORBIDDEN)

        fmt = (request.query_params.get("format") or "xls").lower()
        filters = _filters_from_params(request.query_params)

        if fmt == "pdf":
            content = generate_reporting_pdf(membership.company, **filters)
            response = HttpResponse(content, content_type="application/pdf")
            response["Content-Disposition"] = 'attachment; filename="dealflow_sales_report.pdf"'
            return response

        if fmt == "xls":
            content = generate_reporting_xlsx(membership.company, **filters)
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="dealflow_sales_report.xlsx"'
            return response

        return Response({"detail": "format must be 'pdf' or 'xls'."}, status=status.HTTP_400_BAD_REQUEST)
