from rest_framework.routers import DefaultRouter
from deal_health.views import AnomalyAlertViewSet

router = DefaultRouter()
router.register(r"deal-health/alerts", AnomalyAlertViewSet, basename="anomaly-alert")

urlpatterns = router.urls
