from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import Company, Customer, Membership, Role, User
from catalog.models import Product
from deal_health.models import AnomalyAlert
from deal_health.services import escalate_alert, nudge_rep, run_deal_health_scan
from quotations.models import Quotation, QuotationLine


class DealHealthScanSmokeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Smoke Co")
        self.role_rep, _ = Role.objects.get_or_create(code=Role.SALES_REP, defaults={"label": "Sales Rep"})
        self.owner = User.objects.create_user(email="rep@smoke.test", password="x", full_name="Rep One")
        Membership.objects.create(
            user=self.owner, company=self.company, role=self.role_rep, is_active_default=True
        )
        self.customer = Customer.objects.create(company=self.company, name="ACME", tier="Gold", email="a@acme.test")
        self.product = Product.objects.create(
            company=self.company, name="Widget", category="Hardware", base_price=Decimal("1000.00")
        )
        self.quotation = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=self.owner, status=Quotation.DRAFT
        )
        QuotationLine.objects.create(
            quotation=self.quotation,
            product=self.product,
            qty=1,
            unit_price=Decimal("1000.00"),
            discount_pct=Decimal("0.00"),
            line_total=Decimal("1000.00"),
        )
        # backdate so the stalled-deal rule fires
        Quotation.objects.filter(pk=self.quotation.pk).update(
            updated_at=timezone.now() - timedelta(days=10)
        )

    def test_scan_creates_stalled_alert_without_crashing(self):
        result = run_deal_health_scan(self.company)
        self.assertGreaterEqual(result["new_alerts_count"], 1)
        alert = AnomalyAlert.objects.filter(company=self.company, alert_type=AnomalyAlert.STALLED_DEAL).first()
        self.assertIsNotNone(alert)

    def test_escalate_and_nudge_do_not_crash(self):
        run_deal_health_scan(self.company)
        alert = AnomalyAlert.objects.filter(company=self.company).first()
        self.assertIsNotNone(alert)
        escalate_alert(alert, self.owner, note="test note")
        alert.refresh_from_db()
        self.assertEqual(alert.status, AnomalyAlert.ESCALATED)

        nudge_rep(alert, self.owner)
        alert.refresh_from_db()
        self.assertEqual(alert.status, AnomalyAlert.NUDGED)
