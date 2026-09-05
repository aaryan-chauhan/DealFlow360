"""Approval routing: turns a RiskAssessment into an approval cycle, and applies reviewer
actions. The scoring itself lives in `pricing_discounts.services` (§7.1); this module only
decides who must sign and records what happened.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Role
from audit_log.models import record
from pricing_discounts import services as risk
from quotations.models import Quotation

from .models import ApprovalRequest, ApprovalStep

# Which role may act on which stage. §12: validate against the *current* pending step,
# never "any manager or finance user".
ROLE_FOR_STAGE = {
    ApprovalStep.MANAGER: Role.SALES_MANAGER,
    ApprovalStep.FINANCE: Role.FINANCE_OPS,
}

STAGES_FOR_LEVEL = {
    risk.MANAGER: [ApprovalStep.MANAGER],
    risk.MANAGER_THEN_FINANCE: [ApprovalStep.MANAGER, ApprovalStep.FINANCE],
}


def open_request_for(quotation):
    return quotation.approval_requests.filter(status=ApprovalRequest.PENDING).first()


@transaction.atomic
def route_quotation(quotation, actor, trigger="submit"):
    """Score the quote, cache the score, and open (or skip) an approval cycle.

    Called on submit-for-approval and again on any line edit after submission — the whole
    point of keeping it out of the view is that it must re-run without a user clicking.
    """
    assessment = risk.assess_quotation(quotation)

    quotation.blended_risk_score = assessment.blended_score
    quotation.save(update_fields=["blended_risk_score", "updated_at"])

    # A re-score invalidates any cycle still in flight — the reviewers were looking at
    # different numbers.
    superseded = None
    existing = open_request_for(quotation)
    if existing:
        existing.status = ApprovalRequest.SUPERSEDED
        existing.save(update_fields=["status", "updated_at"])
        superseded = existing
        record(
            quotation.company,
            actor,
            quotation,
            "approval_superseded",
            reason="Quotation lines changed while approval was pending.",
            approval_request_id=str(existing.id),
            trigger=trigger,
        )

    if not assessment.needs_approval:
        # Nothing breached a ceiling — the quote skips review entirely (§7.1).
        if quotation.status != Quotation.APPROVED:
            quotation.set_status(Quotation.APPROVED, actor)
        record(
            quotation.company,
            actor,
            quotation,
            "auto_approved",
            reason="Routing score within policy; no approval required.",
            routing_score=str(assessment.routing_score),
            blended_score=str(assessment.blended_score),
            max_single_overage=str(assessment.max_single_overage),
            trigger=trigger,
        )
        return assessment, None

    request = ApprovalRequest.objects.create(
        quotation=quotation,
        risk_score_snapshot=assessment.routing_score,
        required_level=assessment.required_level,
    )
    for sequence, stage in enumerate(STAGES_FOR_LEVEL[assessment.required_level], start=1):
        ApprovalStep.objects.create(approval_request=request, stage=stage, sequence=sequence)

    if quotation.status != Quotation.PENDING_APPROVAL:
        quotation.set_status(Quotation.PENDING_APPROVAL, actor)

    record(
        quotation.company,
        actor,
        quotation,
        "approval_requested",
        reason=f"Routing score {assessment.routing_score} requires {assessment.required_level}.",
        approval_request_id=str(request.id),
        routing_score=str(assessment.routing_score),
        blended_score=str(assessment.blended_score),
        max_single_overage=str(assessment.max_single_overage),
        required_level=assessment.required_level,
        superseded_request_id=str(superseded.id) if superseded else None,
        trigger=trigger,
    )
    return assessment, request


def reassess_after_line_change(quotation, actor):
    """A line edit on a submitted quote re-runs the engine automatically (§7.1)."""
    if quotation.status == Quotation.DRAFT:
        # Drafts still get a fresh cached score so the builder can show live risk,
        # but nothing is routed until the rep submits.
        assessment = risk.assess_quotation(quotation)
        quotation.blended_risk_score = assessment.blended_score
        quotation.save(update_fields=["blended_risk_score", "updated_at"])
        return assessment, None
    return route_quotation(quotation, actor, trigger="line_edit")


def _guard_actor(request, user, membership):
    step = request.current_step
    if request.status != ApprovalRequest.PENDING or step is None:
        raise ValidationError({"detail": "This approval request is no longer pending."})

    required_role = ROLE_FOR_STAGE[step.stage]
    if membership is None or membership.role.code != required_role:
        raise PermissionDenied(
            f"This step needs {step.get_stage_display()}; your role cannot act on it."
        )
    # Nobody signs off their own deal, whatever their role.
    if request.quotation.owner_id == user.id:
        raise PermissionDenied("You cannot approve your own quotation.")
    return step


@transaction.atomic
def act_on_request(request, user, membership, action, reason=""):
    step = _guard_actor(request, user, membership)

    if action in {ApprovalStep.REJECTED, ApprovalStep.RETURNED} and not reason.strip():
        raise ValidationError({"reason": "A reason is required to reject or return."})

    step.action = action
    step.reviewer = user
    step.reason = reason
    step.acted_at = timezone.now()
    step.save(update_fields=["action", "reviewer", "reason", "acted_at", "updated_at"])

    quotation = request.quotation
    if action == ApprovalStep.APPROVED:
        if request.current_step is None:
            request.status = ApprovalRequest.APPROVED
            quotation.set_status(Quotation.APPROVED, user)
        # else: the chain continues to the next stage, quote stays pending
    elif action == ApprovalStep.REJECTED:
        request.status = ApprovalRequest.REJECTED
        quotation.set_status(Quotation.REJECTED, user)
    else:
        request.status = ApprovalRequest.RETURNED
        quotation.set_status(Quotation.DRAFT, user)

    request.save(update_fields=["status", "updated_at"])

    record(
        quotation.company,
        user,
        quotation,
        f"approval_{action}",
        reason=reason,
        approval_request_id=str(request.id),
        approval_step_id=str(step.id),
        stage=step.stage,
        risk_score_snapshot=str(request.risk_score_snapshot),
    )
    return request
