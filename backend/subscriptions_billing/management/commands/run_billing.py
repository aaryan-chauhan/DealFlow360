"""Recurring billing run (§7.3.4).

This is the Celery Beat job's body, exposed as a management command because Celery is
not wired into this build yet. `--as-of` lets a demo bill a future period without
waiting for the calendar.
"""

from datetime import date

from django.core.management.base import BaseCommand

from accounts.models import Company
from subscriptions_billing.services import due_cycles, run_recurring_billing


class Command(BaseCommand):
    help = "Materialise every due billing cycle into an invoice + invoice line."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Company name (default: every company).")
        parser.add_argument("--as-of", help="Bill as at this date (YYYY-MM-DD).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the cycles that would bill without raising anything.",
        )

    def handle(self, *args, **options):
        company = None
        if options.get("company"):
            company = Company.objects.filter(name=options["company"]).first()
            if company is None:
                raise SystemExit(f"Company '{options['company']}' not found.")

        as_of = date.fromisoformat(options["as_of"]) if options.get("as_of") else None

        if options["dry_run"]:
            cycles = list(due_cycles(company=company, as_of=as_of))
            for cycle in cycles:
                self.stdout.write(
                    f"due  {cycle.subscription.customer.name:<28} "
                    f"{cycle.subscription.product.name:<26} "
                    f"{cycle.period_start} -> {cycle.period_end}  {cycle.amount}"
                )
            self.stdout.write(self.style.SUCCESS(f"\n{len(cycles)} cycle(s) due."))
            return

        result = run_recurring_billing(company=company, as_of=as_of)
        for invoice in result["invoices"]:
            self.stdout.write(
                f"raised   {invoice.invoice_number}  {invoice.customer.name:<28} "
                f"{invoice.total_amount}  "
                f"({len(invoice.recurring_lines)} recurring / "
                f"{len(invoice.one_time_lines)} one-time line(s))"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {len(result['invoices'])} invoice(s) raised as at {result['as_of']}."
            )
        )
