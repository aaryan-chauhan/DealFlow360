"""Upsell / Cross-Sell Engine (spec §7.4).

1. For each product already in the cart, look up `upsell_rule` rows where it is the `source_product`.
2. Filter out products already in cart and any whose implied margin is below `upsell_rule.min_margin_pct`.
3. Rank remaining by `is_promoted` first, then `co_purchase_score` descending.
4. Return top N with an estimated `margin_delta`; writes a `suggestion(status=Suggested)` row per shown recommendation.
5. On rep action: update status to `Added`/`Dismissed`.
"""

from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from approvals.services import reassess_after_line_change
from audit_log.models import record
from catalog.models import Product
from quotations.models import QuotationLine

from .models import Suggestion, UpsellRule

ZERO = Decimal("0.00")


def generate_suggestions_for_quotation(quotation, limit=3):
    """Generates and returns top N recommended product suggestions for a quotation cart."""
    lines = list(quotation.lines.select_related("product"))
    if not lines:
        return []

    cart_product_ids = {line.product_id for line in lines}

    # 1. Look up rules for products in cart
    rules = (
        UpsellRule.objects.filter(
            company=quotation.company,
            source_product_id__in=cart_product_ids,
        )
        .select_related("source_product", "recommended_product")
        .order_by("-is_promoted", "-co_purchase_score")
    )

    # 2. Filter out products already in cart & rank
    candidates = []
    seen_recommended = set()

    for rule in rules:
        rec_product = rule.recommended_product
        if rec_product.id in cart_product_ids or rec_product.id in seen_recommended:
            continue

        # Simple margin estimation: assume 30% margin on list price
        margin_pct = Decimal("30.00")
        if margin_pct < rule.min_margin_pct:
            continue

        seen_recommended.add(rec_product.id)
        margin_delta = (rec_product.base_price * Decimal("0.30")).quantize(Decimal("0.01"))

        candidates.append((rule, rec_product, margin_delta))
        if len(candidates) >= limit:
            break

    # 3. Write / load Suggestion records
    results = []
    for rule, rec_product, margin_delta in candidates:
        suggestion, created = Suggestion.objects.get_or_create(
            quotation=quotation,
            upsell_rule=rule,
            defaults={
                "product": rec_product,
                "margin_delta": margin_delta,
                "status": Suggestion.SUGGESTED,
            },
        )
        results.append(suggestion)

    return results


@transaction.atomic
def add_suggestion_to_quotation(quotation, suggestion_id, actor=None):
    """Rep accepts an upsell suggestion: adds line to cart and updates status to Added."""
    try:
        suggestion = Suggestion.objects.select_related("product", "upsell_rule").get(
            id=suggestion_id, quotation=quotation
        )
    except Suggestion.DoesNotExist:
        raise ValidationError({"detail": "Suggestion not found on this quotation."})

    if suggestion.status == Suggestion.ADDED:
        return suggestion

    product = suggestion.product
    unit_price = product.base_price if product.base_price > ZERO else Decimal("1000.00")
    line_type = QuotationLine.RECURRING if product.is_subscription else QuotationLine.ONE_TIME

    # Check if line already exists or create new
    existing = QuotationLine.objects.filter(quotation=quotation, product=product).first()
    if existing:
        existing.qty += Decimal("1.00")
        existing.save()
    else:
        QuotationLine.objects.create(
            quotation=quotation,
            product=product,
            qty=Decimal("1.00"),
            unit_price=unit_price,
            discount_pct=ZERO,
            line_type=line_type,
        )

    suggestion.status = Suggestion.ADDED
    suggestion.save(update_fields=["status", "updated_at"])

    # Re-run risk engine
    reassess_after_line_change(quotation, actor)

    record(
        quotation.company,
        actor,
        quotation,
        "upsell_suggestion_added",
        reason=f"Added recommended upsell SKU '{product.name}' to quotation.",
        suggestion_id=str(suggestion.id),
        product_id=str(product.id),
    )
    return suggestion


@transaction.atomic
def dismiss_suggestion(quotation, suggestion_id, actor=None):
    """Rep dismisses an upsell suggestion."""
    try:
        suggestion = Suggestion.objects.get(id=suggestion_id, quotation=quotation)
    except Suggestion.DoesNotExist:
        raise ValidationError({"detail": "Suggestion not found on this quotation."})

    suggestion.status = Suggestion.DISMISSED
    suggestion.save(update_fields=["status", "updated_at"])

    record(
        quotation.company,
        actor,
        quotation,
        "upsell_suggestion_dismissed",
        reason=f"Dismissed upsell recommendation for '{suggestion.product.name}'.",
        suggestion_id=str(suggestion.id),
    )
    return suggestion
