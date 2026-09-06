from django.core.management.base import BaseCommand
from accounts.models import Company
from deal_health.models import AnomalyAlert
from deal_health.services import run_deal_health_scan
from quotations.models import Quotation

COMPANY_NAME = "Acme Solutions"


class Command(BaseCommand):
    help = "Seed deal health anomaly alerts for demo tenant"

    def handle(self, *args, **kwargs):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first."))
            return

        # 1. Run live deal health scanner
        stats = run_deal_health_scan(company)
        self.stdout.write(f"scanner complete: {stats['scanned_count']} checked, {stats['new_alerts_count']} new alerts created.")

        # 2. Ensure explicit demo alerts exist for key quotations
        draft_quote = Quotation.objects.filter(company=company, status=Quotation.DRAFT).first()
        pending_quote = Quotation.objects.filter(company=company, status=Quotation.PENDING_APPROVAL).first()

        if draft_quote:
            alert, created = AnomalyAlert.objects.get_or_create(
                company=company,
                quotation=draft_quote,
                alert_type=AnomalyAlert.DISCOUNT_ANOMALY,
                defaults={
                    "severity": AnomalyAlert.HIGH,
                    "status": AnomalyAlert.OPEN,
                    "title": f"Excessive Line Discount on {draft_quote.number}",
                    "description": f"Quotation {draft_quote.number} for {draft_quote.customer.name} contains a line item discount exceeding standard sales baseline limit (15.00%).",
                    "recommended_action": "Review line item discount tier or escalate to Finance Ops.",
                },
            )
            action_str = "created" if created else "reused"
            self.stdout.write(f"{action_str:8} anomaly alert  {alert.title}")

        if pending_quote:
            alert, created = AnomalyAlert.objects.get_or_create(
                company=company,
                quotation=pending_quote,
                alert_type=AnomalyAlert.STALLED_DEAL,
                defaults={
                    "severity": AnomalyAlert.CRITICAL,
                    "status": AnomalyAlert.OPEN,
                    "title": f"Approval Pending > 48 Hours: {pending_quote.number}",
                    "description": f"Pending approval quotation for {pending_quote.customer.name} has been waiting on Manager review for over 48 hours.",
                    "recommended_action": "Send nudge notification to Sales Manager.",
                },
            )
            action_str = "created" if created else "reused"
            self.stdout.write(f"{action_str:8} anomaly alert  {alert.title}")

        self.stdout.write(self.style.SUCCESS("Done. Deal Health anomaly alerts seeded."))
