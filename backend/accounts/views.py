from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Customer
from .permissions import IsCompanyMember
from .scoping import get_membership
from .serializers import (
    CustomerSerializer,
    LoginSerializer,
    LogoutSerializer,
    MembershipSerializer,
    SignupSerializer,
    UserSerializer,
)


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, **tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class CustomerViewSet(viewsets.ModelViewSet):
    """Backs the customer-selection step of the quotation builder (Screen 3)."""

    serializer_class = CustomerSerializer
    permission_classes = [IsCompanyMember]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}

    def get_queryset(self):
        qs = Customer.objects.filter(company=self.membership.company)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_membership(request)
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "active_membership": (
                    MembershipSerializer(membership).data if membership else None
                ),
            }
        )
