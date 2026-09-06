"""Subscription Proration & Billing Engine (spec §7.3).

`prorated_delta` is deliberately framework-agnostic — plain Decimals in, a Decimal out,
no Django imports — matching the shape of the risk engine in `pricing_discounts`, so the
formula in §7.3.2 can be unit-tested on its own. Everything else in this module is the
Django adapter around it, and every entry point is a plain function callable either
synchronously from a view or from a Celery task once Celery is wired.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from audit_log.models import record
from invoicing_payments.models import Invoice
from invoicing_payments.services import (
    add_one_time_line,
    add_recurring_line,
    create_invoice,
    issue_credit_note,
)
from quotations.models import QuotationLine

from .models import BillingCycle, ProrationEvent, Subscription, SubscriptionPlan

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")

# How many unbilled periods are kept materialised ahead of the current one. The billing
# schedule (Screen 10) renders real `billing_cycle` rows rather than dates computed in
# the browser, so the timeline and the thing that actually bills can never disagree.
SCHEDULE_LOOKAHEAD = 4


# ---------------------------------------------------------------------------
# The formula (§7.3.2), isolated from Django
# ---------------------------------------------------------------------------


def prorated_delta(old_qty, new_qty, unit_price, days_remaining, days_in_cycle):
    """delta_amount = (new_qty - old_qty) * unit_price * (days_remaining / days_in_cycle)

    Signed: positive when the customer scales up mid-cycle and owes more, negative when
    they scale down and are owed a credit. Quantised once, at the end, so the day ratio
    keeps full precision through the multiplication.
    """
    if days_in_cycle <= 0:
        return ZERO
    ratio = Decimal(days_remaining) / Decimal(days_in_cycle)
    return ((Decimal(new_qty) - Decimal(old_qty)) * Decimal(unit_price) * ratio).quantize(CENTS)


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


def resolve_plan(product, company):
    """The plan a recurring line becomes. Prefers a plan bound to this exact product
    (§13), then any active plan for the company. Returns None rather than guessing badly
    — the caller skips the line and says so, instead of silently billing on a plan with
    the wrong cycle."""
    plan = SubscriptionPlan.objects.filter(
        company=company, product=product, is_active=True
    ).first()
    if plan is not None:
        return plan
    return SubscriptionPlan.objects.filter(
        company=company, product__isnull=True, is_active=True
    ).first()


def ensure_scheduled_cycles(subscription, lookahead=SCHEDULE_LOOKAHEAD):
    """Materialise upcoming `billing_cycle` rows so the schedule always shows the next
    few periods. Idempotent — re-running tops the schedule back up rather than
    duplicating it."""
    if subscription.status != Subscription.ACTIVE:
        return []

    cycles = list(subscription.billing_cycles.all())
    if not cycles:
        start = subscription.start_date
        end = subscription.plan.period_end_from(start)
        cycles = [
            BillingCycle.objects.create(
                subscription=subscription,
                period_start=start,
                period_end=end,
                amount=subscription.cycle_amount,
            )
        ]

    created = []
    unbilled_ahead = sum(1 for cycle in cycles if not cycle.is_billed)
    cursor = cycles[-1].period_end
    while unbilled_ahead < lookahead:
        cycle = BillingCycle.objects.create(
            subscription=subscription,
            period_start=cursor,
            period_end=subscription.plan.period_end_from(cursor),
            amount=subscription.cycle_amount,
        )
        created.append(cycle)
        cursor = cycle.period_end
        unbilled_ahead += 1
    return created


@transaction.atomic
def create_subscription(*, quotation, plan, product, customer, qty, unit_price, start_date=None):
    """§7.3.1 — `next_bill_date = start_date + cycle_length` on creation.

    The first period is created straight away because it is what the order invoice bills;
    `next_bill_date` therefore points at the *second* period, which is exactly one cycle
    length after the start.
    """
    start_date = start_date or timezone.localdate()
    subscription = Subscription.objects.create(
        quotation=quotation,
        plan=plan,
        product=product,
        customer=customer,
        qty=Decimal(qty),
        unit_price=Decimal(unit_price),
        start_date=start_date,
        next_bill_date=plan.period_end_from(start_date),
    )
    ensure_scheduled_cycles(subscription)
    return subscription


@transaction.atomic
def provision_quotation(quotation, actor=None):
    """Turn a won deal into billing artefacts (§11).

    One order raises exactly one invoice. Its one-time product lines and its first
    recurring subscription charges sit on that same document but in two structurally
    distinct pools — `InvoiceLine.product` for the former, `InvoiceLine.subscription`
    for the latter — which is what lets Screen 13 render them as separate sections and
    what keeps one-time revenue from ever being summed together with recurring revenue.
    """
    if quotation.invoices.exists():
        # Already provisioned. Re-entering (a re-approval, a replayed signal) must not
        # bill the customer twice.
        return {"invoice": quotation.invoices.first(), "subscriptions": [], "skipped": []}

    lines = list(quotation.lines.select_related("product").all())
    if not lines:
        return {"invoice": None, "subscriptions": [], "skipped": []}

    invoice = create_invoice(quotation.customer, Invoice.ONE_TIME, quotation=quotation)
    subscriptions, skipped = [], []

    for line in lines:
        if line.line_type == QuotationLine.ONE_TIME:
            add_one_time_line(
                invoice,
                product=line.product,
                description=line.product.name,
                qty=line.qty,
                unit_price=line.unit_price,
                amount=line.line_total,
            )
            continue

        plan = resolve_plan(line.product, quotation.company)
        if plan is None:
            # No plan configured for this product: leave the line unbilled and say so,
            # rather than inventing a cycle length.
            skipped.append(line.product.name)
            continue

        # The quotation line's discounted per-unit price becomes the subscription's
        # per-cycle unit price, so a negotiated discount carries into every future cycle.
        unit_price = (line.line_total / line.qty).quantize(CENTS) if line.qty else ZERO
        subscription = create_subscription(
            quotation=quotation,
            plan=plan,
            product=line.product,
            customer=quotation.customer,
            qty=line.qty,
            unit_price=unit_price,
        )
        subscriptions.append(subscription)

        first_cycle = subscription.billing_cycles.first()
        invoice_line = add_recurring_line(
            invoice,
            subscription=subscription,
            description=(
                f"{line.product.name} - {plan.name} "
                f"({first_cycle.period_start} to {first_cycle.period_end})"
            ),
            qty=subscription.qty,
            unit_price=subscription.unit_price,
            amount=first_cycle.amount,
        )
        first_cycle.invoice_line = invoice_line
        first_cycle.save(update_fields=["invoice_line", "updated_at"])

    invoice.recompute_total()
    invoice.recompute_status()

    record(
        quotation.company,
        actor,
        invoice,
        "order_invoice_raised",
        invoice_number=invoice.invoice_number,
        quotation=quotation.number,
        one_time_lines=len(invoice.one_time_lines),
        recurring_lines=len(invoice.recurring_lines),
        subscriptions_created=[str(sub.id) for sub in subscriptions],
        skipped_no_plan=skipped,
    )
    return {"invoice": invoice, "subscriptions": subscriptions, "skipped": skipped}


# ---------------------------------------------------------------------------
# Mid-cycle changes (§7.3.2)
# ---------------------------------------------------------------------------


def _target_cycle(subscription, current):
    """Where a mid-cycle adjustment lands.

    The current period if it has not billed yet — the customer simply gets a corrected
    first invoice. Otherwise the next unbilled period, because an invoice that has
    already gone out is not rewritten after the fact (§7.3.2).
    """
    if current is not None and not current.is_billed:
        return current
    after = current.period_end if current is not None else timezone.localdate()
    return (
        subscription.billing_cycles.filter(
            invoice_line__isnull=True, billed_externally=False, period_start__gte=after
        )
        .order_by("period_start")
        .first()
    )


@transaction.atomic
def modify_subscription(
    subscription, actor=None, *, new_qty=None, new_plan=None, effective_date=None, reason=""
):
    """Apply a mid-cycle quantity and/or plan change, writing the arithmetic to a
    `ProrationEvent` and adjusting the billing schedule."""
    if subscription.status != Subscription.ACTIVE:
        raise ValueError("Only an active subscription can be modified.")

    effective_date = effective_date or timezone.localdate()
    current = subscription.current_cycle
    old_qty = subscription.qty
    old_plan = subscription.plan
    new_qty = Decimal(new_qty) if new_qty is not None else old_qty

    if new_qty == old_qty and (new_plan is None or new_plan == old_plan):
        raise ValueError("Nothing to change: quantity and plan are unchanged.")
    if new_qty <= ZERO:
        raise ValueError("Quantity must be greater than zero. Cancel the subscription instead.")

    days_in_cycle = current.days_in_cycle if current else 0
    days_remaining = current.days_remaining(effective_date) if current else 0

    delta = (
        prorated_delta(old_qty, new_qty, subscription.unit_price, days_remaining, days_in_cycle)
        if subscription.plan.prorates
        else ZERO
    )

    subscription.qty = new_qty
    changed_fields = ["qty", "updated_at"]
    if new_plan is not None and new_plan != old_plan:
        subscription.plan = new_plan
        changed_fields.append("plan")
    subscription.save(update_fields=changed_fields)

    boundary = current.period_end if current else effective_date

    # A plan change can alter the cycle length, so every period boundary after the current
    # one is now wrong. Drop the stale look-ahead and let it rebuild on the new cycle
    # length. This has to happen *before* the target cycle is chosen — applying the delta
    # to a row that is about to be deleted would lose the adjustment and leave the
    # proration event pointing at nothing.
    if new_plan is not None and new_plan != old_plan:
        subscription.billing_cycles.filter(
            invoice_line__isnull=True, billed_externally=False, period_start__gte=boundary
        ).delete()
        subscription.next_bill_date = boundary
        subscription.save(update_fields=["next_bill_date", "updated_at"])
    ensure_scheduled_cycles(subscription)

    # Every period from the current one's end onwards bills at the new standard amount.
    # The current period is deliberately excluded: if it has not billed yet it must still
    # charge the *old* rate for the days already served, plus the delta for the rest.
    subscription.billing_cycles.filter(
        invoice_line__isnull=True, billed_externally=False, period_start__gte=boundary
    ).update(amount=subscription.cycle_amount)

    target = _target_cycle(subscription, current)
    if target is not None and delta != ZERO:
        target.refresh_from_db()
        target.amount = (target.amount + delta).quantize(CENTS)
        target.save(update_fields=["amount", "updated_at"])

    event = ProrationEvent.objects.create(
        subscription=subscription,
        billing_cycle=target,
        change_type=(
            ProrationEvent.PLAN_CHANGE
            if (new_plan is not None and new_plan != old_plan)
            else ProrationEvent.QTY_CHANGE
        ),
        delta_amount=delta,
        effective_date=effective_date,
        details={
            "old_qty": str(old_qty),
            "new_qty": str(new_qty),
            "unit_price": str(subscription.unit_price),
            "days_remaining": days_remaining,
            "days_in_cycle": days_in_cycle,
            "old_plan": old_plan.name,
            "new_plan": subscription.plan.name,
            "applied_to_cycle": str(target.id) if target else None,
            "applied_to_period": (
                f"{target.period_start} to {target.period_end}" if target else None
            ),
            "formula": (
                f"({new_qty} - {old_qty}) x {subscription.unit_price} x "
                f"({days_remaining}/{days_in_cycle}) = {delta}"
            ),
            "prorated": subscription.plan.prorates,
            "reason": reason,
        },
    )

    record(
        subscription.company,
        actor,
        subscription,
        "subscription_modified",
        reason=reason,
        old_qty=str(old_qty),
        new_qty=str(new_qty),
        old_plan=old_plan.name,
        new_plan=subscription.plan.name,
        delta_amount=str(delta),
        effective_date=str(effective_date),
        proration_event=str(event.id),
    )
    return event


# ---------------------------------------------------------------------------
# Pause / resume
# ---------------------------------------------------------------------------


@transaction.atomic
def pause_subscription(subscription, actor=None, *, reason=""):
    """Puts billing on hold. `due_cycles()` only ever selects `status=ACTIVE` rows, so a
    paused subscription simply stops being picked up by the recurring billing run — its
    already-scheduled cycles are left exactly where they are rather than dropped, unlike
    cancellation, since a pause is expected to end with the customer resuming."""
    if subscription.status != Subscription.ACTIVE:
        raise ValueError("Only an active subscription can be paused.")

    subscription.status = Subscription.PAUSED
    subscription.paused_at = timezone.now()
    subscription.save(update_fields=["status", "paused_at", "updated_at"])

    record(
        subscription.company,
        actor,
        subscription,
        "subscription_paused",
        reason=reason,
    )
    return subscription


@transaction.atomic
def resume_subscription(subscription, actor=None, *, reason=""):
    """Resumes a paused subscription, shifting every not-yet-billed period and
    `next_bill_date` forward by however many whole days the pause lasted — so the days on
    hold are never billed, and the schedule picks up exactly where it left off rather than
    immediately owing for time the customer could not use the service."""
    if subscription.status != Subscription.PAUSED:
        raise ValueError("Only a paused subscription can be resumed.")

    paused_days = 0
    if subscription.paused_at:
        paused_days = (timezone.now().date() - subscription.paused_at.date()).days

    if paused_days > 0:
        shift = timedelta(days=paused_days)
        unbilled = subscription.billing_cycles.filter(
            invoice_line__isnull=True, billed_externally=False
        )
        for cycle in unbilled:
            cycle.period_start += shift
            cycle.period_end += shift
            cycle.save(update_fields=["period_start", "period_end", "updated_at"])
        subscription.next_bill_date += shift

    subscription.status = Subscription.ACTIVE
    subscription.paused_at = None
    subscription.save(update_fields=["status", "paused_at", "next_bill_date", "updated_at"])
    ensure_scheduled_cycles(subscription)

    record(
        subscription.company,
        actor,
        subscription,
        "subscription_resumed",
        reason=reason,
        paused_days=paused_days,
    )
    return subscription


# ---------------------------------------------------------------------------
# Cancellation (§7.3.3)
# ---------------------------------------------------------------------------


@transaction.atomic
def cancel_subscription(subscription, actor=None, *, reason="", effective_date=None):
    """Apply `subscription_plan.cancellation_rule` and issue the resulting credit note.

    Only money that was actually billed can be refunded, so the refund is measured
    against the current period's *invoiced* amount. If the current period has not been
    invoiced yet there is nothing to hand back — the unbilled periods are simply dropped
    so they never bill.
    """
    if subscription.status != Subscription.ACTIVE:
        raise ValueError("This subscription is not active.")

    effective_date = effective_date or timezone.localdate()
    plan = subscription.plan
    refund_type = plan.refund_type
    current = subscription.current_cycle

    billed_cycle = current if (current is not None and current.is_billed) else None
    billed_amount = billed_cycle.amount if billed_cycle else ZERO
    days_in_cycle = billed_cycle.days_in_cycle if billed_cycle else 0
    days_remaining = billed_cycle.days_remaining(effective_date) if billed_cycle else 0

    if refund_type == SubscriptionPlan.FULL_REFUND:
        credit = billed_amount
    elif refund_type == SubscriptionPlan.PRORATED_REFUND and days_in_cycle:
        credit = (
            billed_amount * Decimal(days_remaining) / Decimal(days_in_cycle)
        ).quantize(CENTS)
    else:
        credit = ZERO

    # Nothing further will be served, so nothing further should bill.
    unbilled = subscription.billing_cycles.filter(
        invoice_line__isnull=True, billed_externally=False
    )
    dropped = unbilled.count()
    unbilled.delete()

    subscription.status = Subscription.CANCELLED
    subscription.cancelled_at = timezone.now()
    subscription.cancellation_reason = reason
    subscription.save(
        update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"]
    )

    event = ProrationEvent.objects.create(
        subscription=subscription,
        billing_cycle=billed_cycle,
        change_type=ProrationEvent.CANCELLATION,
        delta_amount=-credit,
        effective_date=effective_date,
        details={
            "cancellation_rule": refund_type,
            "billed_amount": str(billed_amount),
            "days_remaining": days_remaining,
            "days_in_cycle": days_in_cycle,
            "credit_amount": str(credit),
            "scheduled_cycles_dropped": dropped,
            "formula": (
                f"{refund_type}: {billed_amount} x ({days_remaining}/{days_in_cycle}) = {credit}"
                if refund_type == SubscriptionPlan.PRORATED_REFUND and days_in_cycle
                else f"{refund_type}: credit = {credit}"
            ),
            "reason": reason,
        },
    )

    credit_note = None
    if credit > ZERO:
        # Link to the invoice that carried the charge when there is one; otherwise the
        # note hangs directly off the subscription, which is the case §5.10 calls out.
        source_invoice = (
            billed_cycle.invoice_line.invoice
            if billed_cycle and billed_cycle.invoice_line_id
            else None
        )
        credit_note = issue_credit_note(
            subscription.customer,
            credit,
            reason or f"Cancellation of {subscription.product.name} ({refund_type})",
            invoice=source_invoice,
            subscription=subscription,
            user=actor,
        )

    record(
        subscription.company,
        actor,
        subscription,
        "subscription_cancelled",
        reason=reason,
        cancellation_rule=refund_type,
        credit_amount=str(credit),
        credit_note=str(credit_note.id) if credit_note else None,
        effective_date=str(effective_date),
        scheduled_cycles_dropped=dropped,
    )
    return {"event": event, "credit_note": credit_note, "credit_amount": credit}


# ---------------------------------------------------------------------------
# Recurring billing run (§7.3.4)
# ---------------------------------------------------------------------------


def due_cycles(company=None, as_of=None):
    """Cycles whose period has started and which are not settled yet — no invoice line,
    and not marked as billed outside the system. That is what stops a re-run from
    double-billing a period that already went out."""
    as_of = as_of or timezone.localdate()
    qs = BillingCycle.objects.filter(
        invoice_line__isnull=True,
        billed_externally=False,
        period_start__lte=as_of,
        subscription__status=Subscription.ACTIVE,
    ).select_related("subscription__customer", "subscription__product", "subscription__plan")
    if company is not None:
        qs = qs.filter(subscription__customer__company=company)
    return qs.order_by("subscription__customer__name", "period_start")


@transaction.atomic
def run_recurring_billing(company=None, as_of=None, actor=None):
    """Materialise every due `billing_cycle` into a real invoice + invoice line.

    One invoice per customer per run, carrying only recurring lines — this is the
    scheduled-billing document, structurally distinct from the order invoice that
    `provision_quotation` raises. Advances `next_bill_date` and tops the schedule back
    up so the timeline stays populated.

    Exposed as a management command and an admin-triggerable endpoint because Celery is
    not wired into this build yet; the function itself is already the task body.
    """
    as_of = as_of or timezone.localdate()
    by_customer = {}
    for cycle in due_cycles(company=company, as_of=as_of):
        by_customer.setdefault(cycle.subscription.customer_id, []).append(cycle)

    invoices, touched = [], []
    for cycles in by_customer.values():
        customer = cycles[0].subscription.customer
        invoice = create_invoice(customer, Invoice.RECURRING)

        for cycle in cycles:
            subscription = cycle.subscription
            invoice_line = add_recurring_line(
                invoice,
                subscription=subscription,
                description=(
                    f"{subscription.product.name} - {subscription.plan.name} "
                    f"({cycle.period_start} to {cycle.period_end})"
                ),
                qty=subscription.qty,
                unit_price=subscription.unit_price,
                amount=cycle.amount,
            )
            cycle.invoice_line = invoice_line
            cycle.save(update_fields=["invoice_line", "updated_at"])

            subscription.next_bill_date = cycle.period_end
            subscription.save(update_fields=["next_bill_date", "updated_at"])
            ensure_scheduled_cycles(subscription)
            touched.append(subscription)

        invoice.recompute_total()
        invoice.recompute_status()
        invoices.append(invoice)

        record(
            customer.company,
            actor,
            invoice,
            "recurring_invoice_raised",
            invoice_number=invoice.invoice_number,
            cycles_billed=len(cycles),
            total=str(invoice.total_amount),
            as_of=str(as_of),
        )

    return {"as_of": as_of, "invoices": invoices, "subscriptions": touched}
