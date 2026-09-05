"""Portal routes live under their own `/api/portal/` namespace (§8) so the boundary is
visible in the URL itself: everything below this prefix is token-gated, everything above
it is JWT-gated, and no view is reachable both ways.
"""

from django.urls import path

from .views import (
    PortalCommentView,
    PortalConfirmView,
    PortalCounterOfferView,
    PortalLoginView,
    PortalMyQuotationsView,
    PortalOpenQuotationView,
    PortalQuotationView,
)

urlpatterns = [
    # Literal routes first so "login" / "me" can never be swallowed by the <str:token>
    # patterns below (mirrors the ordering rule already used in quotations/urls.py).
    path("login", PortalLoginView.as_view(), name="portal-login"),
    path("me/quotations/<str:token>", PortalMyQuotationsView.as_view(), name="portal-my-quotations"),
    path(
        "me/quotations/<str:token>/<uuid:quotation_id>/open",
        PortalOpenQuotationView.as_view(),
        name="portal-open-quotation",
    ),
    path("quotations/<str:token>", PortalQuotationView.as_view(), name="portal-quotation"),
    path("<str:token>/comment", PortalCommentView.as_view(), name="portal-comment"),
    path(
        "<str:token>/counter-offer",
        PortalCounterOfferView.as_view(),
        name="portal-counter-offer",
    ),
    path("<str:token>/confirm", PortalConfirmView.as_view(), name="portal-confirm"),
]
