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
]
