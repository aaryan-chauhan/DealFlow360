"""Customer-portal auth and the counter-offer -> re-approval loop (spec §5.9, §7.1, §11).

Two responsibilities, deliberately kept in one module because they are the two halves of
the same security story:

1. `issue_session` / `resolve_token` — the portal's own auth mechanism. It shares nothing
   with SimpleJWT: no `User`, no `Authorization` header, no refresh, no company scope.
2. `apply_counter_offer` / `confirm_quotation` — the customer-side actions, both of which
   re-run the *same* Blended Discount Risk Engine the rep's own edits run through, so a
   customer cannot negotiate past a discount ceiling that a rep could not.
"""

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

from approvals.services import route_quotation
from audit_log.models import record
from accounts.models import Customer
from pricing_discounts import services as risk
from quotations.models import Quotation

from .models import NegotiationMessage, PortalSession

# Namespaces the HMAC so a portal token can never be mistaken for — or forged from — any
# other signed value this project produces.
TOKEN_SALT = "dealflow360.portal.session"
# A distinct salt for the customer-login credential (below) — it is a different kind of
# token (customer-scoped, not quotation-scoped) and must never verify against the wrong
# salt just because both are HMAC-signed with `django.core.signing`.
CUSTOMER_TOKEN_SALT = "dealflow360.portal.customer_login"
CUSTOMER_TOKEN_TTL = timedelta(hours=24)

# The portal can be opened while the quote is live; a confirmed quote is read-only, and a
# draft has not been through governance so it is never shareable.
SHAREABLE_STATUSES = {
    Quotation.PENDING_APPROVAL,
    Quotation.APPROVED,
    Quotation.NEGOTIATION,
    Quotation.CONFIRMED,
}
# Statuses in which the customer may actually act. While a quote sits in
# `pending_approval` the customer sees it but cannot move it — the deal is with the
# internal reviewers, not with them.
ACTIONABLE_STATUSES = {Quotation.APPROVED, Quotation.NEGOTIATION}


class PortalAccessDenied(Exception):
    """Raised for any token that does not resolve to a live, matching session."""

    def __init__(self, detail="This portal link is not valid.", code="invalid_link"):
        self.detail = detail
        self.code = code
        super().__init__(detail)


def _hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def token_ttl():
    return timedelta(hours=int(getattr(settings, "PORTAL_TOKEN_TTL_HOURS", 72)))


@transaction.atomic
def issue_session(quotation, actor=None, ttl=None, revoke_existing=True):
    """Mint a portal link for `quotation`. Returns `(session, raw_token)`.

    The raw token is returned exactly once and never again — only its hash is stored — so
    "re-send the link" always means "issue a new one". Issuing a replacement revokes the
    previous links for this quotation by default: the usual reason a rep re-sends is that
    the old link went to the wrong inbox, and leaving it live would defeat the point.
    """
    if quotation.status not in SHAREABLE_STATUSES:
        raise ValueError(
            f"A quotation in '{quotation.get_status_display()}' cannot be shared with a "
            "customer. Submit it for approval first."
        )

    if revoke_existing:
        now = timezone.now()
        PortalSession.objects.filter(
            quotation=quotation, revoked_at__isnull=True, expires_at__gt=now
        ).update(revoked_at=now)

    session = PortalSession.objects.create(
        quotation=quotation,
        customer=quotation.customer,
        expires_at=timezone.now() + (ttl or token_ttl()),
        issued_by=actor if getattr(actor, "is_authenticated", False) else None,
        # Replaced below; the token can only be signed once the row has an id, and the
        # column is unique so it cannot be left blank on a second concurrent insert.
        token_hash=f"pending:{timezone.now().timestamp()}",
    )

    # The payload carries the session id only. It deliberately does not carry the
    # quotation id: a tampered token fails the HMAC, and even a *validly* signed token can
    # address nothing but its own session row.
    raw_token = signing.dumps({"sid": str(session.id)}, salt=TOKEN_SALT)
    session.token_hash = _hash(raw_token)
    session.save(update_fields=["token_hash", "updated_at"])

    record(
        quotation.company,
        actor,
        quotation,
        "portal_link_issued",
        reason=f"Portal link issued to {quotation.customer.name}.",
        portal_session_id=str(session.id),
        customer_id=str(quotation.customer_id),
        expires_at=session.expires_at.isoformat(),
    )
    return session, raw_token


def resolve_token(raw_token, touch=True):
    """Turn a raw token into its `PortalSession`, or raise `PortalAccessDenied`.

    Four independent gates, in cheapest-first order: HMAC signature, signed-payload age,
    the stored hash, and the row's own expiry/revocation. Signature and expiry failures
    return the same message so probing cannot distinguish "expired" from "forged".
    """
    if not raw_token:
        raise PortalAccessDenied()

    generic = (
        "This portal link is invalid or has expired. Ask your account manager to send a "
        "new one."
    )

    try:
        payload = signing.loads(
            raw_token, salt=TOKEN_SALT, max_age=token_ttl().total_seconds()
        )
    except signing.BadSignature:
        raise PortalAccessDenied(generic)

    session = (
        PortalSession.objects.select_related(
            "quotation", "quotation__customer", "quotation__company", "customer"
        )
        .filter(pk=payload.get("sid"))
        .first()
    )
    # Compared by hash rather than trusting the signature alone, so a link that has been
    # revoked and replaced stops working even though its signature is still valid.
    if session is None or session.token_hash != _hash(raw_token):
        raise PortalAccessDenied(generic)
    if not session.is_active:
        raise PortalAccessDenied(generic, code="expired_link")
    # The pairing from §5.9: the link is only ever valid for the customer it was minted
    # for. A quotation reassigned to a different customer invalidates its old links.
    if session.quotation.customer_id != session.customer_id:
        raise PortalAccessDenied(
            "This portal link no longer matches the quotation it was issued for.",
            code="scope_mismatch",
        )

    if touch:
        session.last_used_at = timezone.now()
        session.save(update_fields=["last_used_at", "updated_at"])
    return session


def authenticate_customer(email, raw_password):
    """Email+password login (spec A1) — a second, independent entry point alongside the
    rep-issued magic link, for a customer who wants to see all of their own quotations
    rather than open one specific link. Returns the matching `Customer` or raises
    `PortalAccessDenied`. A customer's email is only unique *per company* (§5.1), so the
    same address can plausibly belong to a `Customer` row at more than one company —
    each candidate's own password decides which (if any) actually matches, rather than
    guessing from the email alone.
    """
    email = (email or "").strip()
    generic = PortalAccessDenied("Invalid email or password.", code="invalid_credentials")
    if not email or not raw_password:
        raise generic
    candidates = Customer.objects.filter(email__iexact=email).exclude(password_hash="")
    for candidate in candidates:
        if candidate.check_password(raw_password):
            return candidate
    raise generic


def issue_customer_token(customer):
    """A short-lived, customer-scoped credential — never a workspace token, and never
    tied to one quotation the way a magic link is. It only ever proves "this is customer
    X"; every view that accepts it re-derives what that customer may see from
    `customer_id` alone, so it can list and open only that customer's own deals (§12).
    """
    return signing.dumps({"cid": str(customer.id)}, salt=CUSTOMER_TOKEN_SALT)


def resolve_customer_token(raw_token):
    if not raw_token:
        raise PortalAccessDenied("Please log in again.", code="expired_login")
    try:
        payload = signing.loads(
            raw_token, salt=CUSTOMER_TOKEN_SALT, max_age=CUSTOMER_TOKEN_TTL.total_seconds()
        )
    except signing.BadSignature:
        raise PortalAccessDenied("Your session has expired. Please log in again.", code="expired_login")
    customer = Customer.objects.filter(pk=payload.get("cid")).select_related("company").first()
    if customer is None:
        raise PortalAccessDenied("Your session has expired. Please log in again.", code="expired_login")
    return customer


def list_customer_quotations(customer):
    """The "My Quotations" list (§1, §9 Screen 11's portal nav) — only ever this
    customer's own deals, and only those far enough along to mean anything to them; a
    draft the rep hasn't submitted yet is internal work in progress, not theirs to see.
    """
    return (
        Quotation.objects.filter(customer=customer, status__in=SHAREABLE_STATUSES)
        .select_related("company")
        .order_by("-updated_at")
    )


def open_quotation_session(customer, quotation_id):
    """Mints an ordinary single-quotation `PortalSession` for a quotation the logged-in
    customer already owns, reusing `issue_session` unchanged — the resulting token opens
    the exact same detail/negotiation screen a rep-sent magic link does, so every rule
    already enforced there (scope, actionable statuses, the re-approval loop) applies
    without having to be re-taught to a second code path.
    """
    quotation = Quotation.objects.filter(
        pk=quotation_id, customer=customer, status__in=SHAREABLE_STATUSES
    ).first()
    if quotation is None:
        raise PortalAccessDenied("That quotation was not found.", code="scope_mismatch")
    return issue_session(quotation, actor=None)


def assert_scope(session, quotation_id):
    """Explicit guard for a client that names a quotation alongside the token.

    Strictly redundant — the token already resolves to exactly one quotation — but it
    turns a confused-deputy attempt ("here is quote A's token, now act on quote B") into a
    loud 403 rather than a silent write against the wrong record.
    """
    if quotation_id in (None, ""):
        return
    if str(quotation_id) != str(session.quotation_id):
        raise PortalAccessDenied(
            "This portal link is scoped to a different quotation.", code="scope_mismatch"
        )


def assert_actionable(session):
    quotation = session.quotation
    if quotation.status not in ACTIONABLE_STATUSES:
        raise PortalAccessDenied(
            f"This quotation is {quotation.get_status_display().lower()} and cannot be "
            "changed from the portal right now.",
            code="not_actionable",
        )


# --------------------------------------------------------------------------------------
# Customer actions
# --------------------------------------------------------------------------------------


def post_comment(session, body, line=None):
    quotation = session.quotation
    message = NegotiationMessage.objects.create(
        quotation=quotation,
        quotation_line=line,
        author_customer=session.customer,
        message_type=NegotiationMessage.COMMENT,
        body=body,
    )
    record(
        quotation.company,
        None,  # no internal user acted — this came from outside the workspace
        quotation,
        "portal_comment",
        reason=body[:500],
        portal_session_id=str(session.id),
        customer_id=str(session.customer_id),
        customer_name=session.customer.name,
        triggered_by="customer_portal",
    )
    return message


@transaction.atomic
def apply_counter_offer(session, discount_pct, body="", line=None):
    """The heart of §11's negotiation loop.

    A counter-offer is not a wish left in a comment box — it rewrites the terms of the
    quote and then re-runs the *same* `route_quotation` the rep's own edits go through.
    That is the whole point: governance cannot be bypassed by routing an over-ceiling
    discount through the customer instead of the rep.

    The requested percentage is *set* on the targeted lines rather than added to, or
    max()'d with, what is already there, because a counter-offer states the terms the
    customer is asking for. Anything else leaves the quote showing a number neither side
    named, and makes the result depend on the order the offers arrived in.
    """
    quotation = session.quotation
    discount_pct = Decimal(discount_pct).quantize(Decimal("0.01"))

    targets = [line] if line is not None else list(quotation.lines.select_related("product"))
    if not targets:
        raise PortalAccessDenied(
            "This quotation has no lines to negotiate.", code="not_actionable"
        )

    # Negotiation first: an approved quote is locked to internal editing, and moving it
    # here is also what tells the rep's pipeline the deal is live with the customer.
    if quotation.status != Quotation.NEGOTIATION:
        quotation.set_status(Quotation.NEGOTIATION, None)

    previous = []
    for target in targets:
        previous.append(
            {
                "line_id": str(target.id),
                "product": target.product.name,
                "from_pct": str(target.discount_pct),
                "to_pct": str(discount_pct),
            }
        )
        target.discount_pct = discount_pct
        target.save(update_fields=["discount_pct", "line_total", "updated_at"])

    scope_label = line.product.name if line is not None else "the whole quotation"
    message = NegotiationMessage.objects.create(
        quotation=quotation,
        quotation_line=line,
        author_customer=session.customer,
        message_type=NegotiationMessage.COUNTER_OFFER,
        body=body,
        counter_discount_pct=discount_pct,
    )

    record(
        quotation.company,
        None,
        quotation,
        "portal_counter_offer",
        reason=(
            f"{session.customer.name} counter-offered {discount_pct}% on {scope_label}."
            + (f' "{body[:300]}"' if body else "")
        ),
        portal_session_id=str(session.id),
        customer_id=str(session.customer_id),
        customer_name=session.customer.name,
        counter_discount_pct=str(discount_pct),
        scope="line" if line is not None else "quotation",
        lines_changed=previous,
        triggered_by="customer_counter_offer",
    )

    # Re-score against the new terms. `trigger` lands in the routing audit entry, which is
    # what separates this from a rep edit when someone later reads the trail.
    assessment, approval_request = route_quotation(
        quotation, None, trigger="portal_counter_offer"
    )
    quotation.refresh_from_db()

    if approval_request is not None:
        note = (
            f"Counter-offer of {discount_pct}% scores {assessment.routing_score} against "
            "policy, so the quotation has gone back for internal approval. We will come "
            "back to you shortly."
        )
    else:
        note = (
            f"Counter-offer of {discount_pct}% is within policy and has been applied to "
            "the quotation. You can accept it whenever you are ready."
        )
    NegotiationMessage.objects.create(
        quotation=quotation, message_type=NegotiationMessage.SYSTEM, body=note
    )

    return message, assessment, approval_request


@transaction.atomic
def confirm_quotation(session, body=""):
    """Customer acceptance — but only after re-checking the terms actually on the quote.

    Re-running the engine here rather than trusting the stored status closes the window
    where terms changed after the last routing (a counter-offer, or a rep edit made while
    the customer had the tab open). If the current terms breach policy, confirmation is
    refused and the quote is routed for approval instead of silently becoming a won deal
    on numbers nobody signed off.
    """
    quotation = session.quotation
    assessment = risk.assess_quotation(quotation)

    if assessment.needs_approval:
        _, approval_request = route_quotation(
            quotation, None, trigger="portal_confirm_recheck"
        )
        quotation.refresh_from_db()
        NegotiationMessage.objects.create(
            quotation=quotation,
            message_type=NegotiationMessage.SYSTEM,
            body=(
                "The terms currently on this quotation need internal approval before it "
                "can be accepted. It has been sent for review — nothing further is needed "
                "from you."
            ),
        )
        record(
            quotation.company,
            None,
            quotation,
            "portal_confirm_blocked",
            reason=(
                f"{session.customer.name} tried to accept terms scoring "
                f"{assessment.routing_score}, which require {assessment.required_level}."
            ),
            portal_session_id=str(session.id),
            customer_id=str(session.customer_id),
            routing_score=str(assessment.routing_score),
            triggered_by="customer_portal",
        )
        return None, assessment, approval_request

    # Confirmation funnels through `set_status`, which writes the one history row the
    # fulfillment and billing listeners hang off — so accepting from the portal opens the
    # fulfillment order and raises the invoice with no portal-specific wiring at all.
    quotation.set_status(Quotation.CONFIRMED, None)
    message = NegotiationMessage.objects.create(
        quotation=quotation,
        author_customer=session.customer,
        message_type=NegotiationMessage.CONFIRMATION,
        body=body or "Quote accepted.",
    )
    record(
        quotation.company,
        None,
        quotation,
        "portal_confirmed",
        reason=f"{session.customer.name} accepted the quotation from the customer portal.",
        portal_session_id=str(session.id),
        customer_id=str(session.customer_id),
        customer_name=session.customer.name,
        routing_score=str(assessment.routing_score),
        triggered_by="customer_portal",
    )
    quotation.refresh_from_db()
    return message, assessment, None


# --------------------------------------------------------------------------------------
# Internal side
# --------------------------------------------------------------------------------------


def post_internal_reply(quotation, user, body, line=None):
    """A rep/manager reply into the same thread the customer reads (§5.9)."""
    message = NegotiationMessage.objects.create(
        quotation=quotation,
        quotation_line=line,
        author_user=user,
        message_type=NegotiationMessage.COMMENT,
        body=body,
    )
    record(
        quotation.company,
        user,
        quotation,
        "negotiation_reply",
        reason=body[:500],
        triggered_by="internal_workspace",
    )
    return message


def portal_url(raw_token, base_url=None):
    """Absolute link the rep sends the customer.

    `base_url` is normally the requesting workspace's own origin, because the dev setup
    is reached on whatever LAN IP the laptop happens to have that day — hardcoding
    localhost would produce links that only work on the machine that generated them.
    """
    base = (base_url or getattr(settings, "PORTAL_BASE_URL", "") or "").rstrip("/")
    return f"{base}/portal/quotations/{raw_token}"


def send_portal_link_email(quotation, url):
    """Emails the magic link to the customer's real inbox (spec A1) rather than leaving
    delivery entirely to the rep copy-pasting it. Never raises: with no SMTP configured
    this "sends" via Django's console backend (logged, not delivered), and a real send
    failure is logged rather than turned into a 500 on an otherwise-successful link mint —
    the rep still has the URL on screen to copy by hand either way.
    """
    customer = quotation.customer
    if not customer.email:
        return False
    try:
        send_mail(
            subject=f"Your quotation {quotation.number} from {quotation.company.name}",
            message=(
                f"Hi {customer.name},\n\n"
                f"{quotation.owner.full_name or quotation.owner.email} shared quotation "
                f"{quotation.number} with you. Review it, ask questions, or negotiate "
                f"terms here:\n\n{url}\n\n"
                f"This link is private to you and expires "
                f"{int(settings.PORTAL_TOKEN_TTL_HOURS)} hours after it was issued."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to email portal link for quotation %s", quotation.id)
        return False
