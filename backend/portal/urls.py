"""Portal routes live under their own `/api/portal/` namespace (§8) so the boundary is
visible in the URL itself: everything below this prefix is token-gated, everything above
it is JWT-gated, and no view is reachable both ways.
"""

from django.urls import path

from .views import (
    PortalCommentView,
    PortalConfirmView,
    PortalCounterOfferView,
    PortalQuotationView,
)

urlpatterns = [
    path("quotations/<str:token>", PortalQuotationView.as_view(), name="portal-quotation"),
    path("<str:token>/comment", PortalCommentView.as_view(), name="portal-comment"),
    path(
        "<str:token>/counter-offer",
        PortalCounterOfferView.as_view(),
        name="portal-counter-offer",
    ),
    path("<str:token>/confirm", PortalConfirmView.as_view(), name="portal-confirm"),
]
