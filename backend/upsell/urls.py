from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AddSuggestionView,
    DismissSuggestionView,
    QuotationSuggestionsView,
    UpsellRuleViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("upsell-rules", UpsellRuleViewSet, basename="upsell-rule")

urlpatterns = [
    path(
        "quotations/<uuid:quotation_id>/suggestions",
        QuotationSuggestionsView.as_view(),
        name="quotation-suggestions",
    ),
    path(
        "quotations/<uuid:quotation_id>/suggestions/<uuid:sid>/add",
        AddSuggestionView.as_view(),
        name="quotation-suggestion-add",
    ),
    path(
        "quotations/<uuid:quotation_id>/suggestions/<uuid:sid>/dismiss",
        DismissSuggestionView.as_view(),
        name="quotation-suggestion-dismiss",
    ),
    *router.urls,
]
