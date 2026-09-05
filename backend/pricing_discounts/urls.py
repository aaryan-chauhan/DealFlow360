from rest_framework.routers import SimpleRouter

from .views import ApprovalChainRuleViewSet, CategoryCeilingViewSet, DiscountTierViewSet

router = SimpleRouter(trailing_slash=False)
router.register("config/discount-tiers", DiscountTierViewSet, basename="discount-tier")
router.register("config/category-ceilings", CategoryCeilingViewSet, basename="category-ceiling")
router.register("config/approval-chains", ApprovalChainRuleViewSet, basename="approval-chain")

urlpatterns = router.urls
