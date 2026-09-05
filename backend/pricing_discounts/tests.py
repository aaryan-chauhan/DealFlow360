"""Unit tests for the Blended Discount Risk Engine (§7.1).

These exercise `compute_risk` directly — no database, no Django models — which is the
whole reason the engine takes plain dataclasses.
"""

from decimal import Decimal
from unittest import TestCase

from .services import (
    MANAGER,
    MANAGER_THEN_FINANCE,
    NONE,
    ChainRule,
    LineInput,
    compute_risk,
    effective_ceiling,
)

D = Decimal

GOLD_MAX = D("15")
CEILINGS = {"Hardware": D("15"), "Software": D("10"), "Services": D("10")}
RULES = [
    ChainRule(D("0"), D("10"), MANAGER),
    ChainRule(D("10"), D("100"), MANAGER_THEN_FINANCE),
]


def line(category, qty, price, discount, line_id="l1"):
    return LineInput(line_id, category, D(qty), D(price), D(discount))


class EffectiveCeilingTests(TestCase):
    def test_category_ceiling_can_only_tighten(self):
        self.assertEqual(effective_ceiling(GOLD_MAX, CEILINGS, "Services"), D("10"))

    def test_tier_ceiling_wins_when_stricter(self):
        self.assertEqual(effective_ceiling(D("5"), CEILINGS, "Hardware"), D("5"))

    def test_unknown_category_inherits_tier_ceiling(self):
        self.assertEqual(effective_ceiling(GOLD_MAX, CEILINGS, "Subscription"), GOLD_MAX)


class ComputeRiskTests(TestCase):
    def test_within_policy_needs_no_approval(self):
        result = compute_risk([line("Hardware", 10, 80000, 10)], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.routing_score, D("0.00"))
        self.assertEqual(result.required_level, NONE)
        self.assertFalse(result.needs_approval)
        self.assertEqual(result.total_value, D("720000.00"))

    def test_single_line_overage_routes_to_manager(self):
        # Services capped at 10% for a Gold customer; 18% is 8 points over.
        result = compute_risk([line("Services", 10, 5000, 18)], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.max_single_overage, D("8.00"))
        self.assertEqual(result.routing_score, D("8.00"))
        self.assertEqual(result.required_level, MANAGER)

    def test_large_overage_routes_to_manager_then_finance(self):
        result = compute_risk([line("Services", 10, 5000, 25)], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.routing_score, D("15.00"))
        self.assertEqual(result.required_level, MANAGER_THEN_FINANCE)

    def test_max_single_overage_beats_a_diluted_blend(self):
        """The spec's whole point: one badly-over line must not hide inside a big,
        compliant order."""
        lines = [
            line("Hardware", 100, 80000, 5, "big-clean"),  # no overage, huge value
            line("Services", 1, 5000, 30, "small-dirty"),  # 20 points over, tiny value
        ]
        result = compute_risk(lines, GOLD_MAX, CEILINGS, RULES)
        self.assertLess(result.blended_score, D("1"))  # blend alone would look harmless
        self.assertEqual(result.max_single_overage, D("20.00"))
        self.assertEqual(result.routing_score, D("20.00"))  # routing uses the greater
        self.assertEqual(result.required_level, MANAGER_THEN_FINANCE)

    def test_blend_is_value_weighted(self):
        lines = [
            line("Hardware", 1, 100, 20, "a"),  # 5 over ceiling 15, value 80
            line("Hardware", 1, 100, 15, "b"),  # 0 over, value 85
        ]
        result = compute_risk(lines, GOLD_MAX, CEILINGS, RULES)
        # (5 * 80 + 0 * 85) / 165
        self.assertEqual(result.blended_score, D("2.42"))
        self.assertEqual(result.routing_score, D("5.00"))  # max single still governs

    def test_empty_quotation_is_zero_risk_not_a_crash(self):
        result = compute_risk([], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.blended_score, D("0"))
        self.assertEqual(result.required_level, NONE)

    def test_hundred_percent_discount_does_not_divide_by_zero(self):
        result = compute_risk([line("Hardware", 5, 1000, 100)], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.total_value, D("0.00"))
        self.assertEqual(result.blended_score, D("0"))
        self.assertEqual(result.max_single_overage, D("85.00"))
        self.assertEqual(result.required_level, MANAGER_THEN_FINANCE)

    def test_unconfigured_tier_treats_every_discount_as_overage(self):
        result = compute_risk([line("Hardware", 1, 1000, 4)], D("0"), {}, RULES)
        self.assertEqual(result.routing_score, D("4.00"))
        self.assertEqual(result.required_level, MANAGER)

    def test_range_boundary_is_half_open(self):
        """A score of exactly 10 belongs to the [10, 100) rule, not [0, 10)."""
        result = compute_risk([line("Services", 1, 1000, 20)], GOLD_MAX, CEILINGS, RULES)
        self.assertEqual(result.routing_score, D("10.00"))
        self.assertEqual(result.required_level, MANAGER_THEN_FINANCE)
