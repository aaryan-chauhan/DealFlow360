from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import QuotationLineCreateView, QuotationLineDetailView, QuotationViewSet

router = SimpleRouter(trailing_slash=False)
router.register("quotations", QuotationViewSet, basename="quotation")

urlpatterns = [
    path(
        "quotations/<uuid:quotation_id>/lines",
        QuotationLineCreateView.as_view(),
        name="quotation-lines",
    ),
    path(
        "quotations/<uuid:quotation_id>/lines/<uuid:line_id>",
        QuotationLineDetailView.as_view(),
        name="quotation-line",
    ),
    *router.urls,
]
