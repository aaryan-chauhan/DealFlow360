"""Seeds the warehouse slice of spec §13: two warehouses with deliberately staggered
stock, plus demo quotations shaped to force each branch of the split optimiser (§7.2).
Idempotent.

Stock on hand:

    product                  Mumbai WH (1.00)  Bangalore WH (1.60)  total
    Dell Latitude 5440              10                10              20
    Microsoft 365 Business           7                 5              12
    Extended Warranty                4                 3               7
    Onsite Support Plan              6                 6              12
    Training & Onboarding            5                 2               7

The demo quotations below carry no discount, so the risk engine finds nothing over a
ceiling and approves them outright — which means their fulfillment orders are produced by
the real status trigger, not created by hand in this command.

    SPLIT      15x Dell Latitude   -> Mumbai 10 + Bangalore 5, both columns non-zero
    BACKORDER  20x Microsoft 365   -> Mumbai 7 + Bangalore 5, 8 short, BackorderEvent
    SINGLE      4x Training        -> Mumbai 4 only, one shipment
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from accounts.models import Company, Customer, User
from approvals.services import route_quotation
from catalog.models import Product
from quotations.models import Quotation, QuotationLine
from warehouses_fulfillment.models import FulfillmentOrder, StockLevel, Warehouse
from warehouses_fulfillment.services import ensure_fulfillment_order

COMPANY_NAME = "Acme Solutions"

# name, shipping_cost_weight, replenishment_rule
WAREHOUSES = [
    (
        "Mumbai WH",
        Decimal("1.00"),
        {"lead_time_days": 3, "reorder_point": 5, "supplier": "West Zone DC"},
    ),
    (
        "Bangalore WH",
        Decimal("1.60"),
        {"lead_time_days": 6, "reorder_point": 4, "supplier": "South Zone DC"},
    ),
]

# product name -> {warehouse name: qty_on_hand}
STOCK = {
    "Dell Latitude 5440": {"Mumbai WH": 10, "Bangalore WH": 10},
    "Microsoft 365 Business": {"Mumbai WH": 7, "Bangalore WH": 5},
    "Extended Warranty": {"Mumbai WH": 4, "Bangalore WH": 3},
    "Onsite Support Plan": {"Mumbai WH": 6, "Bangalore WH": 6},
    "Training & Onboarding": {"Mumbai WH": 5, "Bangalore WH": 2},
    "HP EliteBook 840": {"Mumbai WH": 8, "Bangalore WH": 6},
    "Cloud Backup Service": {"Mumbai WH": 50, "Bangalore WH": 50},
}

# owner email, customer name, [(product, qty)], what it proves
DEMO_QUOTATIONS = [
    (
        "rohan@company.com",
        "Acme Technologies Pvt Ltd",
        [("Dell Latitude 5440", 15)],
        "SPLIT: 15 needed, no single warehouse holds 15 -> 10 Mumbai + 5 Bangalore.",
    ),
    (
        "karan@company.com",
        "Global Retail Ltd",
        [("Microsoft 365 Business", 20)],
        "BACKORDER: 20 needed, only 12 exist anywhere -> 7 + 5 and 8 short.",
    ),
    (
        "rohan@company.com",
        "TechCorp Solutions",
        [("Training & Onboarding", 4)],
        "SINGLE: 4 needed, Mumbai alone covers it -> one shipment.",
    ),
]

PLANNABLE_STATUSES = [Quotation.APPROVED, Quotation.CONFIRMED]


class Command(BaseCommand):
    help = "Seed warehouses, staggered stock and demo quotations that force each split branch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Drop existing fulfillment orders and clear all stock reservations before "
                "re-planning. Use this to re-run a demo after accepting or overriding."
            ),
        )

    def find_demo_quotation(self, company, owner, customer, lines):
        """Match on the exact (customer, owner, line) shape so a re-run reuses the demo
        quote instead of piling up a new Q-number every time."""
        wanted = sorted((name, Decimal(qty)) for name, qty in lines)
        for quotation in Quotation.objects.filter(
            company=company, owner=owner, customer=customer
        ):
            actual = sorted(
                (line.product.name, line.qty)
                for line in quotation.lines.select_related("product")
            )
            if actual == wanted:
                return quotation
        return None

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first.")

        if options["reset"]:
            dropped = FulfillmentOrder.objects.filter(quotation__company=company).delete()[0]
            # .update() bypasses StockLevel.save(), so qty_available is recomputed
            # explicitly here — with nothing reserved it is simply everything on hand.
            StockLevel.objects.filter(warehouse__company=company).update(
                qty_reserved=Decimal("0.00"), qty_available=F("qty_on_hand")
            )
            self.stdout.write(f"reset    dropped {dropped} fulfillment row(s), cleared holds")

        for name, weight, rule in WAREHOUSES:
            warehouse, created = Warehouse.objects.get_or_create(
                company=company,
                name=name,
                defaults={"shipping_cost_weight": weight, "replenishment_rule": rule},
            )
            self.stdout.write(
                f"{'created' if created else 'reused '}  warehouse   {warehouse.name} "
                f"(cost weight {warehouse.shipping_cost_weight})"
            )

        warehouses = {w.name: w for w in Warehouse.objects.filter(company=company)}

        self.stdout.write("")
        for product_name, per_warehouse in STOCK.items():
            product = Product.objects.filter(company=company, name=product_name).first()
            if product is None:
                self.stdout.write(
                    self.style.WARNING(f"skipped  product     {product_name} not seeded")
                )
                continue
            for warehouse_name, qty in per_warehouse.items():
                level, created = StockLevel.objects.get_or_create(
                    warehouse=warehouses[warehouse_name],
                    product=product,
                    defaults={"qty_on_hand": Decimal(qty)},
                )
                if not created and options["reset"]:
                    # Only --reset rewinds stock to the demo numbers. A plain re-run must
                    # leave qty_on_hand alone: restocking a product by hand and then
                    # re-running the seed is exactly the backorder-consolidation
                    # workflow, and silently rewinding it makes the watcher look broken.
                    level.qty_on_hand = Decimal(qty)
                    level.save(update_fields=["qty_on_hand"])
                self.stdout.write(
                    f"stock    {product.name:<26} {warehouse_name:<13} "
                    f"on hand {level.qty_on_hand:>6}  available {level.qty_available:>6}"
                )

        self.stdout.write("")
        for owner_email, customer_name, lines, note in DEMO_QUOTATIONS:
            owner = User.objects.get(email=owner_email)
            customer = Customer.objects.filter(company=company, name=customer_name).first()
            if customer is None:
                self.stdout.write(
                    self.style.WARNING(f"skipped  customer    {customer_name} not seeded")
                )
                continue

            quotation = self.find_demo_quotation(company, owner, customer, lines)
            if quotation:
                self.stdout.write(
                    f"reused   quotation   {quotation.number} ({quotation.status})  {note}"
                )
                continue

            quotation = Quotation.objects.create(
                company=company, customer=customer, owner=owner
            )
            for product_name, qty in lines:
                product = Product.objects.get(company=company, name=product_name)
                QuotationLine.objects.create(
                    quotation=quotation,
                    product=product,
                    qty=Decimal(qty),
                    unit_price=product.base_price,
                    discount_pct=Decimal("0.00"),
                    line_type=(
                        QuotationLine.RECURRING
                        if product.is_subscription
                        else QuotationLine.ONE_TIME
                    ),
                )
            assessment, _ = route_quotation(quotation, owner)
            quotation.refresh_from_db()
            self.stdout.write(
                f"created  quotation   {quotation.number}  {customer.name}  "
                f"routing score {assessment.routing_score} -> {quotation.status}"
            )
            self.stdout.write(f"         {note}")

        # Anything already approved (including the phase-3 quotes, approved before any
        # warehouse existed) gets its split planned now.
        self.stdout.write("")
        planned = 0
        for quotation in Quotation.objects.filter(
            company=company, status__in=PLANNABLE_STATUSES
        ):
            order = ensure_fulfillment_order(quotation)
            if order is None:
                continue
            planned += 1
            self.stdout.write(
                f"planned  {quotation.number}  {quotation.customer.name:<28} "
                f"{order.get_status_display():<22} {order.shipment_count} shipment(s), "
                f"promised {order.promised_date}"
            )
            for line in order.split_lines.select_related("warehouse", "product"):
                tag = "BACKORDER" if line.is_backorder else "         "
                self.stdout.write(
                    f"         {tag} {line.product.name:<26} x{line.qty_fulfilled:<8} "
                    f"{line.warehouse.name:<13} cost {line.cost}"
                )

        if planned == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No approved/confirmed quotation found, so nothing was planned."
                )
            )
        self.stdout.write(self.style.SUCCESS(f"\nDone. {planned} fulfillment order(s)."))
