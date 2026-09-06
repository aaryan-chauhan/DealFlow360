from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response

from accounts.models import Role
from accounts.permissions import IsCompanyMember
from accounts.scoping import get_membership, scope_to_owner
from approvals.serializers import ApprovalRequestSerializer
from approvals.services import reassess_after_line_change, route_quotation

from .models import Quotation, QuotationLine
from .serializers import (
    BulkDiscountSerializer,
    QuotationDetailSerializer,
    QuotationLineSerializer,
    QuotationListSerializer,
)


def assessment_payload(assessment):
    return {
        "blended_score": str(assessment.blended_score),
        "max_single_overage": str(assessment.max_single_overage),
        "routing_score": str(assessment.routing_score),
        "required_level": assessment.required_level,
        "needs_approval": assessment.needs_approval,
        "total_value": str(assessment.total_value),
        "lines": [
            {
                "line_id": line.line_id,
                "category": line.category,
                "discount_pct": str(line.discount_pct),
                "ceiling_pct": str(line.ceiling_pct),
                "overage_pct": str(line.overage_pct),
                "line_value": str(line.line_value),
            }
            for line in assessment.lines
        ],
    }


class QuotationScopedMixin:
    permission_classes = [IsCompanyMember]

    @property
    def membership(self):
        membership = get_membership(self.request)
        if membership is None:
            raise PermissionDenied("No company membership for this user.")
        return membership

    def scoped_quotations(self):
        """Reps only ever see their own pipeline — enforced in the queryset, never in
        the UI (§12)."""
        qs = Quotation.objects.filter(company=self.membership.company).select_related(
            "customer", "owner"
        )
        return scope_to_owner(qs, self.membership, self.request.user)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}

    def assert_editable(self, quotation):
        if quotation.status not in Quotation.EDITABLE_STATUSES:
            raise ValidationError(
                {"detail": f"A quotation in '{quotation.get_status_display()}' cannot be edited."}
            )
        if (
            self.membership.role.code == Role.SALES_REP
            and quotation.owner_id != self.request.user.id
        ):
            raise PermissionDenied("You can only edit your own quotations.")


class QuotationViewSet(QuotationScopedMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = self.scoped_quotations().prefetch_related("lines__product", "status_history")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        owner = self.request.query_params.get("owner")
        if owner:
            qs = qs.filter(owner_id=owner)
        return qs

    def get_serializer_class(self):
        return QuotationListSerializer if self.action == "list" else QuotationDetailSerializer

    def perform_create(self, serializer):
        serializer.save(company=self.membership.company, owner=self.request.user)

    def perform_update(self, serializer):
        self.assert_editable(serializer.instance)
        serializer.save()

    @action(detail=True, methods=["post"], url_path="submit-for-approval")
    def submit_for_approval(self, request, pk=None):
        quotation = self.get_object()
        if quotation.status not in {Quotation.DRAFT, Quotation.NEGOTIATION}:
            raise ValidationError(
                {"detail": f"Only a draft can be submitted (this one is {quotation.status})."}
            )
        if self.membership.role.code == Role.SALES_REP and quotation.owner_id != request.user.id:
            raise PermissionDenied("You can only submit your own quotations.")
        if not quotation.lines.exists():
            raise ValidationError({"detail": "Add at least one line before submitting."})

        assessment, approval_request = route_quotation(quotation, request.user)
        quotation.refresh_from_db()
        return Response(
            {
                "quotation": QuotationDetailSerializer(
                    quotation, context=self.get_serializer_context()
                ).data,
                "assessment": assessment_payload(assessment),
                "approval_request": (
                    ApprovalRequestSerializer(approval_request).data if approval_request else None
                ),
            }
        )

    @action(detail=True, methods=["post"], url_path="bulk-discount")
    def bulk_discount(self, request, pk=None):
        """Order-level discount (§B3) — one percentage applied to every line at once,
        rather than a rep editing each line by hand. Same editability/ownership guard
        and risk re-scoring as a single-line edit."""
        quotation = self.get_object()
        self.assert_editable(quotation)
        if (
            self.membership.role.code == Role.SALES_REP
            and quotation.owner_id != request.user.id
        ):
            raise PermissionDenied("You can only edit your own quotations.")

        serializer = BulkDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discount_pct = serializer.validated_data["discount_pct"]

        lines = list(quotation.lines.all())
        if not lines:
            raise ValidationError({"detail": "Add at least one line before applying a discount."})
        for line in lines:
            line.discount_pct = discount_pct
            line.save(update_fields=["discount_pct", "line_total", "updated_at"])

        assessment, _ = reassess_after_line_change(quotation, request.user)
        quotation.refresh_from_db()
        return Response(
            {
                "quotation": QuotationDetailSerializer(
                    quotation, context=self.get_serializer_context()
                ).data,
                "assessment": assessment_payload(assessment),
            }
        )

    def assert_owned_or_privileged(self, quotation, verb):
        """A rep may only reach into their own deals; every other role sees the company."""
        if (
            self.membership.role.code == Role.SALES_REP
            and quotation.owner_id != self.request.user.id
        ):
            raise PermissionDenied(f"You can only {verb} your own quotations.")

    @action(detail=True, methods=["post"], url_path="generate-portal-link")
    def generate_portal_link(self, request, pk=None):
        """Mint the customer's magic link (§5.9).

        This is the one place the two auth worlds touch, and they touch in exactly one
        direction: an authenticated internal user asks for a token, and gets back a string
        that is useless anywhere except `/api/portal/`. The raw token is returned once and
        never stored, so re-sending a link always means issuing a fresh one.
        """
        from portal.serializers import PortalSessionSerializer
        from portal.services import issue_session, portal_url, send_portal_link_email

        quotation = self.get_object()
        self.assert_owned_or_privileged(quotation, "send")

        try:
            session, raw_token = issue_session(quotation, request.user)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        # An explicit setting wins; otherwise the link is built from the origin the rep is
        # actually using, so a LAN address produces a LAN-reachable link.
        base_url = settings.PORTAL_BASE_URL or request.headers.get("Origin") or ""
        url = portal_url(raw_token, base_url)
        emailed = send_portal_link_email(quotation, url)
        return Response(
            {
                "token": raw_token,
                "portal_url": url,
                "emailed": emailed,
                "session": PortalSessionSerializer(session).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="negotiation")
    def negotiation(self, request, pk=None):
        """The negotiation thread, seen and answered from the internal workspace.

        Same rows the portal reads — one thread, two auth boundaries (§5.9). Without this
        the rep would be negotiating blind, answering in email while the customer types
        into a portal nobody internal can see.
        """
        from portal.serializers import NegotiationMessageSerializer
        from portal.services import post_internal_reply

        quotation = self.get_object()
        messages = quotation.negotiation_messages.select_related(
            "author_user", "author_customer", "quotation_line__product"
        )

        if request.method == "GET":
            return Response(NegotiationMessageSerializer(messages, many=True).data)

        self.assert_owned_or_privileged(quotation, "reply on")
        body = (request.data.get("body") or "").strip()
        if not body:
            raise ValidationError({"body": "A message cannot be empty."})

        line = None
        line_id = request.data.get("quotation_line")
        if line_id:
            line = get_object_or_404(QuotationLine, pk=line_id, quotation=quotation)

        message = post_internal_reply(quotation, request.user, body, line=line)
        return Response(
            NegotiationMessageSerializer(message).data, status=status.HTTP_201_CREATED
        )


class QuotationLineCreateView(QuotationScopedMixin, CreateAPIView):
    serializer_class = QuotationLineSerializer

    def get_quotation(self):
        return get_object_or_404(self.scoped_quotations(), pk=self.kwargs["quotation_id"])

    def create(self, request, *args, **kwargs):
        """Adding a product already on the quote tops up that line instead of opening a
        second one. Enforced here rather than in the picker so every path — the product
        screen, a repeated POST, a double-clicked button — lands on one line per
        (product, variant). Two rows for the same product would also distort the risk
        engine, which weights each line's overage by its own value (§7.1).
        """
        quotation = self.get_quotation()
        self.assert_editable(quotation)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        existing = QuotationLine.objects.filter(
            quotation=quotation,
            product=serializer.validated_data["product"],
            variant=serializer.validated_data.get("variant"),
        ).first()

        if existing is None:
            serializer.save(quotation=quotation)
            payload, code = serializer.data, status.HTTP_201_CREATED
        else:
            # The existing unit_price and discount stand: the price is a deliberate
            # snapshot from when the line was first added (§5.4), and the picker has no
            # discount field, so taking its default 0 would silently wipe a discount the
            # rep had already negotiated on the review step.
            existing.qty += serializer.validated_data["qty"]
            existing.save()
            payload = QuotationLineSerializer(existing).data
            payload["merged"] = True
            code = status.HTTP_200_OK

        # An edit after submission re-runs the risk engine automatically (§7.1).
        assessment, _ = reassess_after_line_change(quotation, request.user)
        return Response(
            {"line": payload, "assessment": assessment_payload(assessment)}, status=code
        )


class QuotationLineDetailView(QuotationScopedMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = QuotationLineSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_quotation(self):
        return get_object_or_404(self.scoped_quotations(), pk=self.kwargs["quotation_id"])

    def get_object(self):
        return get_object_or_404(
            QuotationLine, pk=self.kwargs["line_id"], quotation=self.get_quotation()
        )

    def update(self, request, *args, **kwargs):
        quotation = self.get_quotation()
        self.assert_editable(quotation)
        line = self.get_object()
        serializer = self.get_serializer(line, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        assessment, _ = reassess_after_line_change(quotation, request.user)
        return Response({"line": serializer.data, "assessment": assessment_payload(assessment)})

    def destroy(self, request, *args, **kwargs):
        quotation = self.get_quotation()
        self.assert_editable(quotation)
        self.get_object().delete()
        reassess_after_line_change(quotation, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
