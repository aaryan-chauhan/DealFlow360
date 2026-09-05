from rest_framework.routers import SimpleRouter

from .views import ApprovalViewSet

router = SimpleRouter(trailing_slash=False)
router.register("approvals", ApprovalViewSet, basename="approval")

urlpatterns = router.urls
