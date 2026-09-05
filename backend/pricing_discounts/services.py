"""Blended Discount Risk Engine (spec §7.1).

`compute_risk` is deliberately framework-agnostic — plain dataclasses in, plain
dataclass out, no Django imports — so it is unit-testable on its own and can be called
synchronously from a view or from a Celery task. `assess_quotation` is the thin Django
adapter that loads the governance config for a quotation and delegates to it.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

ZERO = Decimal("0")
HUNDRED = Decimal("100")

NONE = "none"
MANAGER = "manager"
MANAGER_THEN_FINANCE = "manager_then_finance"


@dataclass(frozen=True)
class LineInput:
    """One cart line as the engine sees it."""

    line_id: str
    category: str
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal


@dataclass(frozen=True)
class ChainRule:
    """A half-open [range_from, range_to) → required approval level mapping."""

    range_from: Decimal
    range_to: Decimal
    required_level: str

    def covers(self, score: Decimal) -> bool:
        return self.range_from <= score < self.range_to


@dataclass(frozen=True)
class LineAssessment:
    line_id: str
    category: str
    discount_pct: Decimal
    ceiling_pct: Decimal
    overage_pct: Decimal
    line_value: Decimal


@dataclass(frozen=True)
class RiskAssessment:
    blended_score: Decimal
    max_single_overage: Decimal
    routing_score: Decimal
    required_level: str
    total_value: Decimal
    lines: Sequence[LineAssessment] = field(default_factory=tuple)

    @property
    def needs_approval(self) -> bool:
        return self.required_level != NONE


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def effective_ceiling(
    tier_max_pct: Decimal, category_ceilings: dict, category: str
) -> Decimal:
    """The stricter of the tier ceiling and the category override (§7.1).

    A category with no override inherits the tier ceiling — the override can only ever
    tighten the cap, never loosen it.
    """
    category_pct = category_ceilings.get(category)
    if category_pct is None:
        return tier_max_pct
    return min(tier_max_pct, category_pct)


def compute_risk(
    lines: Sequence[LineInput],
    tier_max_pct: Decimal,
    category_ceilings: dict,
    chain_rules: Sequence[ChainRule],
) -> RiskAssessment:
    assessed = []
    for line in lines:
        ceiling = effective_ceiling(tier_max_pct, category_ceilings, line.category)
        overage = max(ZERO, Decimal(line.discount_pct) - ceiling)
        line_value = (
            Decimal(line.qty)
            * Decimal(line.unit_price)
            * (Decimal("1") - Decimal(line.discount_pct) / HUNDRED)
        )
        assessed.append(
            LineAssessment(
                line_id=line.line_id,
                category=line.category,
                discount_pct=_q2(line.discount_pct),
                ceiling_pct=_q2(ceiling),
                overage_pct=_q2(overage),
                line_value=_q2(line_value),
            )
        )

    total_value = sum((a.line_value for a in assessed), ZERO)
    weighted = sum((a.overage_pct * a.line_value for a in assessed), ZERO)

    # A fully-discounted (or empty) quote has no value to weight by; treat as no risk
    # rather than dividing by zero — the max-single-overage term still catches abuse.
    blended = _q2(weighted / total_value) if total_value > ZERO else ZERO
    max_single = _q2(max((a.overage_pct for a in assessed), default=ZERO))

    # Use the greater of the two so one badly-over line can never hide inside an
    # otherwise-low blended average.
    routing_score = max(blended, max_single)

    # The score measures *overage*, so zero means nothing breached a ceiling and the
    # quote skips review — without this a rule seeded as [0, 10) would trap every
    # perfectly compliant deal.
    required_level = NONE
    if routing_score > ZERO:
        for rule in chain_rules:
            if rule.covers(routing_score):
                required_level = rule.required_level
                break

    return RiskAssessment(
        blended_score=blended,
        max_single_overage=max_single,
        routing_score=routing_score,
        required_level=required_level,
        total_value=_q2(total_value),
        lines=tuple(assessed),
    )


def load_governance(company, customer_tier_name):
    """Reads the admin-configured ceilings for one customer tier (Django-facing)."""
    from .models import ApprovalChainRule, DiscountTier

    tier = (
        DiscountTier.objects.filter(company=company, name__iexact=customer_tier_name)
        .prefetch_related("category_ceilings")
        .first()
    )
    # No configured tier means no sanctioned discount at all — every discount becomes
    # overage and routes for review rather than silently passing.
    tier_max_pct = tier.max_discount_pct if tier else ZERO
    category_ceilings = (
        {c.category: c.max_discount_pct for c in tier.category_ceilings.all()} if tier else {}
    )
    chain_rules = [
        ChainRule(r.discount_range_from, r.discount_range_to, r.required_level)
        for r in ApprovalChainRule.objects.filter(company=company).order_by(
            "discount_range_from"
        )
    ]
    return tier_max_pct, category_ceilings, chain_rules


def assess_quotation(quotation) -> RiskAssessment:
    """Django adapter: pull the quote's lines + its customer's governance config."""
    tier_max_pct, category_ceilings, chain_rules = load_governance(
        quotation.company, quotation.customer.tier
    )
    lines = [
        LineInput(
            line_id=str(line.id),
            category=line.product.category,
            qty=line.qty,
            unit_price=line.unit_price,
            discount_pct=line.discount_pct,
        )
        for line in quotation.lines.select_related("product")
    ]
    return compute_risk(lines, tier_max_pct, category_ceilings, chain_rules)
