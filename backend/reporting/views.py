from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSalesManager
from accounts.scoping import get_membership
from reporting.services import generate_reporting_csv, get_reporting_summary


class ReportingSummaryView(APIView):
    permission_classes = [IsSalesManager]

    def get(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Active membership required"}, status=status.HTTP_403_FORBIDDEN)

        rep_id = request.query_params.get("sales_rep")
        date_range = request.query_params.get("date_range")

        data = get_reporting_summary(membership.company, sales_rep_id=rep_id, date_range=date_range)
        return Response(data, status=status.HTTP_200_OK)


class ReportingExportView(APIView):
    permission_classes = [IsSalesManager]

    def get(self, request):
        membership = get_membership(request)
        if not membership:
            return Response({"detail": "Active membership required"}, status=status.HTTP_403_FORBIDDEN)

        rep_id = request.query_params.get("sales_rep")
        csv_content = generate_reporting_csv(membership.company, sales_rep_id=rep_id)

        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="dealflow_sales_report.csv"'
        return response
