from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrReadOnly, IsCompanyMember
from accounts.scoping import get_membership
from quotations.models import Quotation

from .models import Suggestion, UpsellRule
from .serializers import SuggestionSerializer, UpsellRuleSerializer
from .services import (
    add_suggestion_to_quotation,
    dismiss_suggestion,
    generate_suggestions_for_quotation,
)


class QuotationSuggestionsView(APIView):
    """Returns upsell recommendations for a specific quotation (spec §8)."""

    permission_classes = [IsCompanyMember]

    def get(self, request, quotation_id):
        membership = get_membership(request)
        quotation = get_object_or_404(Quotation, pk=quotation_id, company=membership.company)
        
        # Generate & load active suggestions
        suggestions = generate_suggestions_for_quotation(quotation)
        active_suggestions = quotation.suggestions.exclude(status=Suggestion.DISMISSED)
        
        return Response(SuggestionSerializer(active_suggestions, many=True).data)


class AddSuggestionView(APIView):
    """Rep adds a suggested upsell item to the quotation cart."""

    permission_classes = [IsCompanyMember]

    def post(self, request, quotation_id, sid):
        membership = get_membership(request)
        quotation = get_object_or_404(Quotation, pk=quotation_id, company=membership.company)
        suggestion = add_suggestion_to_quotation(quotation, sid, actor=request.user)
        return Response(SuggestionSerializer(suggestion).data, status=status.HTTP_200_OK)


class DismissSuggestionView(APIView):
    """Rep dismisses an upsell suggestion."""

    permission_classes = [IsCompanyMember]

    def post(self, request, quotation_id, sid):
        membership = get_membership(request)
        quotation = get_object_or_404(Quotation, pk=quotation_id, company=membership.company)
        suggestion = dismiss_suggestion(quotation, sid, actor=request.user)
        return Response(SuggestionSerializer(suggestion).data, status=status.HTTP_200_OK)


class UpsellRuleViewSet(viewsets.ModelViewSet):
    """Admin CRUD for cross-sell pairing rules."""

    serializer_class = UpsellRuleSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_value_regex = "[0-9a-f-]{36}"

    def get_queryset(self):
        membership = get_membership(self.request)
        if membership is None:
            return UpsellRule.objects.none()
        return UpsellRule.objects.filter(company=membership.company).select_related(
            "source_product", "recommended_product"
        )

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(company=membership.company)
