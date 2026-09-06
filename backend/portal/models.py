from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Customer, TimeStampedModel, User, UUIDModel
from quotations.models import Quotation, QuotationLine


class PortalSession(UUIDModel, TimeStampedModel):
    """The security boundary of the customer portal (§5.9).

    A session is bound to exactly one `(quotation, customer)` pair and carries its own
    expiry. It is deliberately *not* a `User`, not a JWT, and not stored in an auth
    header — the raw token is the URL, and the only endpoints that will look at it live
    under `/api/portal/`. That is what makes "the token can never be reused to see a
    different quotation" a structural property rather than a check someone has to
    remember to write: the token does not name a quotation, it names a session, and the
    session names the quotation.

    Only a SHA-256 of the raw token is stored. A leaked database dump therefore cannot be
    replayed as a portal link, exactly as with a password hash.
    """

    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="portal_sessions"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="portal_sessions"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    # Set when the rep issues a replacement link. Kept rather than deleted so the audit
    # trail can still show that a link existed and when it was withdrawn.
    revoked_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_sessions"
    )

    class Meta:
        db_table = "portal_session"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["token_hash"])]

    def __str__(self):
        return f"portal link for {self.quotation.number} -> {self.customer.name}"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_active(self):
        return self.revoked_at is None and not self.is_expired


class NegotiationMessage(UUIDModel):
    """The comment / counter-offer thread on a quotation (§5.9).

    Two nullable author columns rather than one polymorphic "author" because either side
    can post and the two sides are genuinely different tables: `author_user` is internal
    staff, `author_customer` is the external party. Exactly one is set on a human message
    (enforced by a check constraint); both are null on a `system` note, which is how the
    thread records "this counter-offer sent the quote back for approval" without
    attributing it to a person who did not write it.
    """

    COMMENT = "comment"
    COUNTER_OFFER = "counter_offer"
    DELIVERY_DATE_REQUEST = "delivery_date_request"
    CONFIRMATION = "confirmation"
    SYSTEM = "system"
    TYPE_CHOICES = [
        (COMMENT, "Comment"),
        (COUNTER_OFFER, "Counter-offer"),
        (DELIVERY_DATE_REQUEST, "Delivery date request"),
        (CONFIRMATION, "Confirmation"),
        (SYSTEM, "System"),
    ]

    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="negotiation_messages"
    )
    # Optional: a counter-offer aimed at one line rather than the whole quote. SET_NULL
    # so deleting a line does not erase the negotiation history that referenced it.
    quotation_line = models.ForeignKey(
        QuotationLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiation_messages",
    )
    author_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="negotiation_messages"
    )
    author_customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiation_messages",
    )
    message_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default=COMMENT)
    body = models.TextField(blank=True)
    # What the risk engine reads to decide whether this counter-offer re-triggers an
    # approval cycle (§5.9, §7.1).
    counter_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    # Set only on a `delivery_date_request` message — the date the customer is asking
    # fulfillment to promise, not a commitment until a rep or Finance/Ops acts on it.
    requested_delivery_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "negotiation_message"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                check=~(
                    models.Q(author_user__isnull=False) & models.Q(author_customer__isnull=False)
                ),
                name="chk_negotiation_single_author",
            )
        ]

    def __str__(self):
        return f"{self.message_type} on {self.quotation_id}"

    @property
    def author_side(self):
        """`customer` / `internal` / `system` — what the thread UI colours by."""
        if self.author_customer_id:
            return "customer"
        if self.author_user_id:
            return "internal"
        return "system"

    @property
    def author_name(self):
        if self.author_customer_id:
            return self.author_customer.name
        if self.author_user_id:
            return self.author_user.full_name or self.author_user.email
        return "DealFlow360"
