"""Portal endpoints (§8) — the only routes in the project that accept a portal token, and
the only routes that accept *no* internal credential at all.

Every view here sets `authentication_classes = []`. That is not a shortcut: it means DRF
never runs `JWTAuthentication` on these paths, so `request.user` is always anonymous and
there is no code path by which an internal session could widen what a portal caller sees.
The reverse holds too — a portal token is not a JWT and is not sent in an `Authorization`
header, so presenting one to any `/api/...` endpoint is simply an unauthenticated request.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from quotations.models import QuotationLine

from .serializers import (
    CommentInputSerializer,
    ConfirmInputSerializer,
    CounterOfferInputSerializer,
    CustomerLoginSerializer,
    CustomerQuotationSummarySerializer,
    DeliveryDateInputSerializer,
    NegotiationMessageSerializer,
    PortalQuotationSerializer,
)
from .services import (
    PortalAccessDenied,
    apply_counter_offer,
    assert_actionable,
    assert_scope,
    authenticate_customer,
    confirm_quotation,
    issue_customer_token,
    list_customer_quotations,
    open_quotation_session,
    post_comment,
    request_delivery_date,
    resolve_customer_token,
    resolve_token,
)


def denied_response(exc):
    """403 for a scope violation, 401 for a link that does not resolve.

    The distinction matters when reading logs: a 401 is an expired or forged link, a 403
    is a live link being pointed at something it was not issued for.
    """
    code = status.HTTP_403_FORBIDDEN if exc.code == "scope_mismatch" else (
        status.HTTP_409_CONFLICT if exc.code == "not_actionable" else status.HTTP_401_UNAUTHORIZED
    )
    return Response({"detail": exc.detail, "code": exc.code}, status=code)


class PortalBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def handle_exception(self, exc):
        if isinstance(exc, PortalAccessDenied):
            return denied_response(exc)
        return super().handle_exception(exc)

    def session_from(self, token):
        return resolve_token(token)

    def resolve_line(self, session, line_id):
        """A line id from the customer is only ever looked up *within* the token's own
        quotation — a line id belonging to someone else's quote simply does not exist."""
        if not line_id:
            return None
        line = QuotationLine.objects.filter(
            pk=line_id, quotation_id=session.quotation_id
        ).select_related("product").first()
        if line is None:
            raise PortalAccessDenied(
                "That line is not part of this quotation.", code="scope_mismatch"
            )
        return line

    def payload(self, session, extra=None):
        session.quotation.refresh_from_db()
        data = {
            "quotation": PortalQuotationSerializer(session.quotation).data,
            "session": {
                "expires_at": session.expires_at,
                "customer_name": session.customer.name,
            },
        }
        if extra:
            data.update(extra)
        return data


class PortalQuotationView(PortalBaseView):
    """GET /api/portal/quotations/{token}"""

    def get(self, request, token):
        session = self.session_from(token)
        return Response(self.payload(session))


class PortalCommentView(PortalBaseView):
    """POST /api/portal/{token}/comment"""

    def post(self, request, token):
        session = self.session_from(token)
        serializer = CommentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assert_scope(session, serializer.validated_data.get("quotation"))
        assert_actionable(session)

        line = self.resolve_line(session, serializer.validated_data.get("quotation_line"))
        message = post_comment(session, serializer.validated_data["body"], line=line)
        return Response(
            self.payload(session, {"message": NegotiationMessageSerializer(message).data}),
            status=status.HTTP_201_CREATED,
        )


class PortalDeliveryDateView(PortalBaseView):
    """POST /api/portal/{token}/request-delivery-date

    A request, not a commitment — it lands in the shared thread for a rep or Finance/Ops
    to act on (e.g. adjusting the fulfillment order's promised date) rather than silently
    changing anything itself.
    """

    def post(self, request, token):
        session = self.session_from(token)
        serializer = DeliveryDateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assert_scope(session, serializer.validated_data.get("quotation"))
        assert_actionable(session)

        line = self.resolve_line(session, serializer.validated_data.get("quotation_line"))
        message = request_delivery_date(
            session,
            serializer.validated_data["requested_delivery_date"],
            body=serializer.validated_data.get("body", ""),
            line=line,
        )
        return Response(
            self.payload(session, {"message": NegotiationMessageSerializer(message).data}),
            status=status.HTTP_201_CREATED,
        )


class PortalCounterOfferView(PortalBaseView):
    """POST /api/portal/{token}/counter-offer

    Rewrites the targeted lines and re-runs the Blended Discount Risk Engine (§7.1). The
    response tells the customer plainly whether their offer landed or went for review —
    but never the score, the ceiling, or who is reviewing it.
    """

    def post(self, request, token):
        session = self.session_from(token)
        serializer = CounterOfferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assert_scope(session, serializer.validated_data.get("quotation"))
        assert_actionable(session)

        line = self.resolve_line(session, serializer.validated_data.get("quotation_line"))
        message, assessment, approval_request = apply_counter_offer(
            session,
            serializer.validated_data["counter_discount_pct"],
            body=serializer.validated_data.get("body", ""),
            line=line,
        )
        return Response(
            self.payload(
                session,
                {
                    "message": NegotiationMessageSerializer(message).data,
                    "sent_for_approval": approval_request is not None,
                    "outcome": (
                        "pending_internal_approval"
                        if approval_request is not None
                        else "accepted_within_policy"
                    ),
                },
            ),
            status=status.HTTP_201_CREATED,
        )


class PortalConfirmView(PortalBaseView):
    """POST /api/portal/{token}/confirm"""

    def post(self, request, token):
        session = self.session_from(token)
        serializer = ConfirmInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assert_scope(session, serializer.validated_data.get("quotation"))
        assert_actionable(session)

        message, assessment, approval_request = confirm_quotation(
            session, body=serializer.validated_data.get("body", "")
        )
        confirmed = message is not None
        return Response(
            self.payload(
                session,
                {
                    "confirmed": confirmed,
                    "sent_for_approval": approval_request is not None,
                    "outcome": "confirmed" if confirmed else "pending_internal_approval",
                },
            ),
            status=status.HTTP_200_OK,
        )


class PortalLoginView(PortalBaseView):
    """POST /api/portal/login — the customer's second entry point (spec A1) alongside a
    rep-issued magic link: email + password, in exchange for a customer-scoped token that
    can list and open this customer's own quotations. Never a `User`, never JWT, never
    workspace-wide — see the module docstring in `services.py`."""

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = authenticate_customer(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        return Response(
            {
                "customer_token": issue_customer_token(customer),
                "customer": {"name": customer.name, "email": customer.email},
            }
        )


class PortalMyQuotationsView(PortalBaseView):
    """GET /api/portal/me/quotations/{customer_token} — "My Quotations" (§1, §9)."""

    def get(self, request, token):
        customer = resolve_customer_token(token)
        quotations = list_customer_quotations(customer)
        return Response(
            {
                "customer": {"name": customer.name, "email": customer.email},
                "quotations": CustomerQuotationSummarySerializer(quotations, many=True).data,
            }
        )


class PortalOpenQuotationView(PortalBaseView):
    """POST /api/portal/me/quotations/{customer_token}/{quotation_id}/open

    Mints an ordinary single-quotation session for one of the logged-in customer's own
    deals and hands back its token — the caller then simply opens
    `/portal/quotations/{token}` exactly as it would for a rep-sent magic link, so the
    entire negotiation screen is reused unchanged rather than re-implemented for this
    second entry point.
    """

    def post(self, request, token, quotation_id):
        customer = resolve_customer_token(token)
        session, raw_token = open_quotation_session(customer, quotation_id)
        return Response({"token": raw_token}, status=status.HTTP_201_CREATED)
