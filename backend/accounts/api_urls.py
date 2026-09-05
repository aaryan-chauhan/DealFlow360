from django.urls import path
from rest_framework.routers import SimpleRouter

from .dashboard_views import DashboardSummaryView
from .views import CustomerViewSet

router = SimpleRouter(trailing_slash=False)
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls + [
    path("dashboard/summary", DashboardSummaryView.as_view(), name="dashboard-summary"),
]

