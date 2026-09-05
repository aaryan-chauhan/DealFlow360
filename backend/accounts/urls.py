from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, SignupView

urlpatterns = [
    path("signup", SignupView.as_view(), name="auth-signup"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("refresh", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me", MeView.as_view(), name="auth-me"),
]
