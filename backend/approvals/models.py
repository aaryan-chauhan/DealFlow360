from decimal import Decimal

from django.db import models

from accounts.models import TimeStampedModel, User, UUIDModel
from quotations.models import Quotation


class ApprovalRequest(UUIDModel, TimeStampedModel):
    """Created only when the risk engine decides review is needed. One per approval
    *cycle* — a later re-negotiation opens a second request with its own snapshot (§5.5).
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (RETURNED, "Returned"),
        (SUPERSEDED, "Superseded"),
    ]

    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="approval_requests"
    )
    # Frozen at submission time — kept separate from the live score on the quotation
    # because a re-negotiation triggers a second cycle with a different snapshot.
    risk_score_snapshot = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    required_level = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        db_table = "approval_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quotation.number} ({self.required_level}, {self.status})"

    @property
    def current_step(self):
        """The step that must act next — everything RBAC keys off (§12)."""
        return self.steps.filter(action=ApprovalStep.PENDING).order_by("sequence").first()


class ApprovalStep(UUIDModel, TimeStampedModel):
    """One row per reviewer in the chain: a request can have 1 or 2 steps, each with its
    own reviewer, action and reason for the audit trail (§5.5)."""

    MANAGER = "manager"
    FINANCE = "finance"
    STAGE_CHOICES = [(MANAGER, "Sales Manager"), (FINANCE, "Finance / Ops")]

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    ACTION_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (RETURNED, "Returned"),
    ]

    approval_request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name="steps"
    )
    stage = models.CharField(max_length=16, choices=STAGE_CHOICES)
    sequence = models.PositiveSmallIntegerField(default=1)
    # Null until someone acts; PROTECT so a reviewer who has acted can never be deleted
    # out from under the audit trail.
    reviewer = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="approval_steps"
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, default=PENDING)
    reason = models.TextField(blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "approval_step"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["approval_request", "sequence"], name="uniq_step_request_sequence"
            )
        ]

    def __str__(self):
        return f"{self.stage} #{self.sequence}: {self.action}"
