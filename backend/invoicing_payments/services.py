"""Invoice, payment and credit-note operations (spec §5.10, §7.3.3-4).

`add_one_time_line` and `add_recurring_line` are deliberately two functions rather than
one with a flag. Every invoice line in the system is built through one of them, so there
is no code path that could set both `product` and `subscription`, or neither — the
database constraint on `InvoiceLine` is the backstop, not the first line of defence.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from audit_log.models import record

from .models import CreditNote, Invoice, InvoiceLine, Payment

ZERO = Decimal("0.00")
DEFAULT_PAYMENT_TERM_DAYS = 15


def create_invoice(customer, invoice_type, quotation=None, due_days=DEFAULT_PAYMENT_TERM_DAYS):
    issue_date = timezone.localdate()
    return Invoice.objects.create(
        customer=customer,
        quotation=quotation,
        invoice_type=invoice_type,
        status=Invoice.ISSUED,
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=due_days),
    )


def add_one_time_line(invoice, *, product, description, qty, unit_price, amount):
    """A product charge. `subscription` is never set here."""
    return InvoiceLine.objects.create(
        invoice=invoice,
        product=product,
        subscription=None,
        description=description,
        qty=Decimal(qty),
        unit_price=Decimal(unit_price),
        amount=Decimal(amount).quantize(Decimal("0.01")),
    )


def add_recurring_line(invoice, *, subscription, description, qty, unit_price, amount):
    """A subscription charge for one billing period. `product` is never set here — the
    product is reachable through `subscription.product`, and duplicating it onto the line
    is exactly the merge this module exists to prevent."""
    return InvoiceLine.objects.create(
        invoice=invoice,
        product=None,
        subscription=subscription,
        description=description,
        qty=Decimal(qty),
        unit_price=Decimal(unit_price),
        amount=Decimal(amount).quantize(Decimal("0.01")),
    )


@transaction.atomic
def record_payment(invoice, user, amount, method=Payment.BANK_TRANSFER, reference=""):
    """Records a payment and re-derives the invoice status. Partial payments are normal —
    the status is computed from the sum of payments and credits, never set by the caller."""
    payment = Payment.objects.create(
        invoice=invoice,
        amount=Decimal(amount).quantize(Decimal("0.01")),
        method=method,
        reference=reference,
        recorded_by=user if getattr(user, "is_authenticated", False) else None,
    )
    invoice.refresh_from_db()
    invoice.recompute_status()

    record(
        invoice.company,
        user,
        invoice,
        "payment_recorded",
        reason=reference,
        amount=str(payment.amount),
        method=method,
        invoice_number=invoice.invoice_number,
        balance_due=str(invoice.balance_due),
        new_status=invoice.status,
    )
    return payment


@transaction.atomic
def issue_credit_note(customer, amount, reason, *, invoice=None, subscription=None, user=None):
    """Issues a credit note. `invoice` stays null on the cancellation path where no
    specific invoice is involved — the note then hangs directly off the subscription
    (§5.10)."""
    note = CreditNote.objects.create(
        invoice=invoice,
        subscription=subscription,
        customer=customer,
        amount=Decimal(amount).quantize(Decimal("0.01")),
        reason=reason,
        issued_by=user if getattr(user, "is_authenticated", False) else None,
    )
    if invoice is not None:
        invoice.refresh_from_db()
        invoice.recompute_status()

    record(
        customer.company,
        user,
        note,
        "credit_note_issued",
        reason=reason,
        amount=str(note.amount),
        invoice_number=invoice.invoice_number if invoice else None,
        subscription_id=str(subscription.id) if subscription else None,
    )
    return note


def invoice_summary_text(invoice):
    """Plain-text summary behind `GET /api/invoices/{id}/download-summary`.

    The two pools are rendered as two blocks with their own subtotals, mirroring what
    Screen 13 shows — the separation is a property of the document, not of the web view.
    """
    lines = [
        f"INVOICE {invoice.invoice_number}",
        f"Customer   : {invoice.customer.name} ({invoice.customer.tier})",
        f"Issued     : {invoice.issue_date}   Due: {invoice.due_date or '-'}",
        f"Type       : {invoice.get_invoice_type_display()}",
        f"Status     : {invoice.get_status_display()}",
    ]
    if invoice.quotation_id:
        lines.append(f"Quotation  : {invoice.quotation.number}")
    lines.append("")

    for title, pool, subtotal in (
        ("ONE-TIME ITEMS", invoice.one_time_lines, invoice.one_time_subtotal),
        ("RECURRING ITEMS", invoice.recurring_lines, invoice.recurring_subtotal),
    ):
        if not pool:
            continue
        lines.append(title)
        lines.append("-" * len(title))
        for line in pool:
            lines.append(
                f"  {line.description:<52} {line.qty:>8} x {line.unit_price:>12} "
                f"= {line.amount:>14}"
            )
        lines.append(f"  {'Subtotal':<52} {subtotal:>40}")
        lines.append("")

    lines += [
        f"{'TOTAL':<54} {invoice.total_amount:>40}",
        f"{'Paid':<54} {invoice.amount_paid:>40}",
    ]
    if invoice.amount_credited > ZERO:
        lines.append(f"{'Credited':<54} {invoice.amount_credited:>40}")
    lines.append(f"{'BALANCE DUE':<54} {invoice.balance_due:>40}")
    return "\n".join(lines)
