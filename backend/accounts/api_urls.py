"""Non-auth accounts endpoints that live under /api/ rather than /api/auth/."""

from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet

router = SimpleRouter(trailing_slash=False)
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls
