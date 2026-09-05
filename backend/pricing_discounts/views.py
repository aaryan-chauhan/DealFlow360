from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import CanConfigureDiscounts
from accounts.scoping import get_membership

from .models import ApprovalChainRule, CategoryDiscountCeiling, DiscountTier
from .serializers import (
    ApprovalChainRuleSerializer,
    CategoryDiscountCeilingSerializer,
    DiscountTierSerializer,
)


class DiscountConfigViewSet(viewsets.ModelViewSet):
    """Admin configures everything here; Sales Manager may also edit discount config (§3)."""

    permission_classes = [CanConfigureDiscounts]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}


class DiscountTierViewSet(DiscountConfigViewSet):
    serializer_class = DiscountTierSerializer

    def get_queryset(self):
        return DiscountTier.objects.filter(company=self.membership.company).prefetch_related(
            "category_ceilings"
        )

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "approval_rules": list(
                ApprovalChainRule.objects.filter(company=self.membership.company)
            ),
        }

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company)


class CategoryCeilingViewSet(DiscountConfigViewSet):
    serializer_class = CategoryDiscountCeilingSerializer

    def get_queryset(self):
        qs = CategoryDiscountCeiling.objects.filter(
            discount_tier__company=self.membership.company
        ).select_related("discount_tier")
        tier_id = self.request.query_params.get("discount_tier")
        if tier_id:
            qs = qs.filter(discount_tier_id=tier_id)
        return qs


class ApprovalChainRuleViewSet(DiscountConfigViewSet):
    serializer_class = ApprovalChainRuleSerializer

    def get_queryset(self):
        return ApprovalChainRule.objects.filter(company=self.membership.company)

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company)
