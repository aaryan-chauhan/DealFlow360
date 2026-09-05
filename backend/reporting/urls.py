from django.urls import path
from reporting.views import ReportingExportView, ReportingSummaryView

urlpatterns = [
    path("reports/summary", ReportingSummaryView.as_view(), name="reporting-summary"),
    path("reports/export", ReportingExportView.as_view(), name="reporting-export"),
]
