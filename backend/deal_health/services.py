from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from audit_log.models import record as log_event
from deal_health.models import AnomalyAlert
from quotations.models import Quotation
from warehouses_fulfillment.models import FulfillmentOrder


def run_deal_health_scan(company):
    """Scans company quotations and fulfillment orders to generate/update anomaly alerts (§7.3)."""
    now = timezone.now()
    scanned_count = 0
    new_alerts_count = 0

    # 1. Stalled Deals (> 3 days inactive for active pipeline quotes)
    stalled_cutoff = now - timedelta(days=3)
    active_quotes = Quotation.objects.filter(
        company=company,
        status__in=[Quotation.DRAFT, Quotation.PENDING_APPROVAL],
        updated_at__lt=stalled_cutoff,
    )

    for q in active_quotes:
        scanned_count += 1
        alert, created = AnomalyAlert.objects.get_or_create(
            company=company,
            quotation=q,
            alert_type=AnomalyAlert.STALLED_DEAL,
            status__in=[AnomalyAlert.OPEN, AnomalyAlert.NUDGED, AnomalyAlert.ESCALATED],
            defaults={
                "severity": AnomalyAlert.HIGH if q.total_amount > Decimal("500000.00") else AnomalyAlert.MEDIUM,
                "title": f"Stalled Quotation {q.number} ({q.customer.name})",
                "description": f"Quotation in status '{q.status}' has had no activity since {q.updated_at.strftime('%Y-%m-%d')}. Value: ₹{q.total_amount:,.2f}.",
                "recommended_action": "Follow up with customer or nudge quote owner.",
            },
        )
        if created:
            new_alerts_count += 1

    # 2. Discount Anomalies (> 15% discount on line items)
    high_discount_quotes = Quotation.objects.filter(
        company=company,
        status__in=[Quotation.DRAFT, Quotation.PENDING_APPROVAL],
        lines__discount_pct__gt=Decimal("15.00"),
    ).distinct()

    for q in high_discount_quotes:
        scanned_count += 1
        max_discount = max([line.discount_pct for line in q.lines.all()] or [Decimal("0.00")])
        alert, created = AnomalyAlert.objects.get_or_create(
            company=company,
            quotation=q,
            alert_type=AnomalyAlert.DISCOUNT_ANOMALY,
            status__in=[AnomalyAlert.OPEN, AnomalyAlert.NUDGED, AnomalyAlert.ESCALATED],
            defaults={
                "severity": AnomalyAlert.CRITICAL if max_discount > Decimal("20.00") else AnomalyAlert.HIGH,
                "title": f"High Discount Anomaly on {q.number}",
                "description": f"Line item discount of {max_discount}% exceeds standard sales baseline (15.00%). Total quote value: ₹{q.total_amount:,.2f}.",
                "recommended_action": "Requires Sales Manager approval or discount reduction.",
            },
        )
        if created:
            new_alerts_count += 1

    # 3. Delivery Slippage (Backordered fulfillment orders)
    backordered_orders = FulfillmentOrder.objects.filter(
        quotation__company=company,
        status=FulfillmentOrder.BACKORDERED,
    )

    for fo in backordered_orders:
        scanned_count += 1
        q = fo.quotation
        alert, created = AnomalyAlert.objects.get_or_create(
            company=company,
            quotation=q,
            alert_type=AnomalyAlert.DELIVERY_SLIPPAGE,
            status__in=[AnomalyAlert.OPEN, AnomalyAlert.NUDGED, AnomalyAlert.ESCALATED],
            defaults={
                "severity": AnomalyAlert.CRITICAL,
                "title": f"Stock Backorder Slippage on {q.number}",
                "description": f"Fulfillment order {fo.order_number} is backordered due to inventory shortage. Promised delivery: {fo.promised_date or 'TBD'}.",
                "recommended_action": "Escalate to Ops / Warehouse lead for stock replenishment.",
            },
        )
        if created:
            new_alerts_count += 1

    return {
        "scanned_count": scanned_count,
        "new_alerts_count": new_alerts_count,
        "total_active_alerts": AnomalyAlert.objects.filter(company=company, status__in=[AnomalyAlert.OPEN, AnomalyAlert.NUDGED, AnomalyAlert.ESCALATED]).count(),
    }


def escalate_alert(alert, user, note=""):
    """Escalates alert to upper management and logs audit event."""
    alert.status = AnomalyAlert.ESCALATED
    alert.escalated_at = timezone.now()
    alert.escalated_by_name = user.full_name or user.email
    alert.escalation_note = note
    alert.save()

    log_event(
        user.company,
        user,
        alert,
        "ESCALATE_ALERT",
        reason=note,
    )
    return alert


def nudge_rep(alert, user):
    """Sends a reminder/nudge to the quotation owner."""
    alert.status = AnomalyAlert.NUDGED
    alert.nudge_count += 1
    alert.last_nudged_at = timezone.now()
    alert.save()

    log_event(
        user.company,
        user,
        alert,
        "NUDGE_REP",
        reason=f"Nudge count: {alert.nudge_count}",
    )
    return alert
