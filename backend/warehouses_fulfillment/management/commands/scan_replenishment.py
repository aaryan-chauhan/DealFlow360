"""CLI form of the backorder-consolidation watcher (§7.2.6 / §14).

Celery Beat is not wired into this build yet, so the watcher runs either from here or
from `POST /api/fulfillment/scan-replenishment`. It only flags lines whose stock has
caught up — nothing is applied without an operator accepting the consolidation.
"""

from django.core.management.base import BaseCommand

from accounts.models import Company
from warehouses_fulfillment.services import scan_backorder_replenishment


class Command(BaseCommand):
    help = "Flag backorder lines whose warehouse stock has been replenished."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Company name to scan (default: all).")

    def handle(self, *args, **options):
        company = None
        if options.get("company"):
            company = Company.objects.filter(name=options["company"]).first()
            if company is None:
                raise SystemExit(f"Company '{options['company']}' not found.")

        result = scan_backorder_replenishment(company=company)

        for line in result["flagged"]:
            self.stdout.write(
                f"flagged  {line.fulfillment_order.quotation.number}  {line.product.name} "
                f"x{line.qty_fulfilled} @ {line.warehouse.name} — ready to consolidate"
            )
        for line in result["cleared"]:
            self.stdout.write(
                f"cleared  {line.fulfillment_order.quotation.number}  {line.product.name} "
                f"@ {line.warehouse.name} — stock no longer sufficient"
            )
        if not result["flagged"] and not result["cleared"]:
            self.stdout.write("No change: no backorder line's stock position moved.")
        self.stdout.write(self.style.SUCCESS("Done."))
