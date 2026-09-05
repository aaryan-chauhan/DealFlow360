"""Master seed command that runs the full seed sequence top-to-bottom (§13).

Runs:
1. seed_accounts — Company, Roles, Admin/Manager/Finance/Rep Users, Customer records
2. seed_catalog — Products (Hardware, Services, Subscriptions), Variants, Price Lists & Items
3. seed_pricing — Discount Tiers (Bronze/Silver/Gold), Category Ceilings, Approval Chain Rules
4. seed_quotations — Seed Quotations across Draft, Pending Approval, Approved, Negotiation, Confirmed
5. seed_fulfillment — Warehouses (Main, East Depot), Stock Levels, Fulfillment Orders & Splits
6. seed_subscriptions — Subscription Plans, Active Subscriptions & Invoices
7. seed_portal — Active Customer Portal session & opening thread message
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Runs all seed commands in phase order to fully initialize the DealFlow360 demo dataset."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Starting DealFlow360 Master Seed Process ==="))
        
        commands = [
            ("accounts", "seed_accounts"),
            ("catalog", "seed_catalog"),
            ("pricing_discounts", "seed_pricing"),
            ("upsell", "seed_upsell"),
            ("quotations", "seed_quotations"),
            ("warehouses_fulfillment", "seed_fulfillment"),
            ("subscriptions_billing", "seed_subscriptions"),
            ("portal", "seed_portal"),
            ("deal_health", "seed_deal_health"),
        ]


        for step, command_name in commands:
            self.stdout.write(self.style.HTTP_INFO(f"\n---> Running {command_name}..."))
            try:
                call_command(command_name)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Failed running {command_name}: {exc}"))
                raise exc

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=================================================="))
        self.stdout.write(self.style.SUCCESS("  Master Seed Process Completed Successfully!"))
        self.stdout.write(self.style.SUCCESS("  All demo accounts, products, quotes, splits,"))
        self.stdout.write(self.style.SUCCESS("  subscriptions & portal links are ready for demo."))
        self.stdout.write(self.style.SUCCESS("=================================================="))
