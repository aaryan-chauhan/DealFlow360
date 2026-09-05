from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("accounts.api_urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("pricing_discounts.urls")),
    path("api/", include("quotations.urls")),
    path("api/", include("approvals.urls")),
    path("api/", include("warehouses_fulfillment.urls")),
    path("api/", include("subscriptions_billing.urls")),
    path("api/", include("invoicing_payments.urls")),
    path("api/", include("upsell.urls")),
    path("api/", include("deal_health.urls")),
    path("api/", include("reporting.urls")),
    # Its own namespace, not folded into the "api/" includes above: everything under
    # /api/portal/ is gated by a portal token and nothing else (§8).
    path("api/portal/", include("portal.urls")),
]

