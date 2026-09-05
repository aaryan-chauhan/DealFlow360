from decimal import Decimal

from django.test import TestCase

from accounts.models import Company, Customer, Membership, Role, User
from catalog.models import Product
from quotations.models import Quotation, QuotationLine
from reporting.services import generate_reporting_csv, get_reporting_summary


class ReportingSmokeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Smoke Co")
        role_rep, _ = Role.objects.get_or_create(code=Role.SALES_REP, defaults={"label": "Sales Rep"})
        self.owner = User.objects.create_user(email="rep@smoke.test", password="x", full_name="Rep One")
        Membership.objects.create(
            user=self.owner, company=self.company, role=role_rep, is_active_default=True
        )
        self.customer = Customer.objects.create(company=self.company, name="ACME", tier="Gold", email="a@acme.test")
        self.product = Product.objects.create(
            company=self.company, name="Widget", category="Hardware", base_price=Decimal("1000.00")
        )
        self.quotation = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=self.owner, status=Quotation.CONFIRMED
        )
        QuotationLine.objects.create(
            quotation=self.quotation,
            product=self.product,
            qty=Decimal("2.00"),
            unit_price=Decimal("1000.00"),
            discount_pct=Decimal("10.00"),
            line_total=Decimal("1800.00"),
        )

    def test_summary_does_not_crash(self):
        data = get_reporting_summary(self.company)
        self.assertEqual(data["summary"]["total_revenue"], 1800.0)
        self.assertEqual(data["summary"]["confirmed_count"], 1)
        self.assertEqual(len(data["top_skus"]), 1)
        self.assertEqual(data["top_skus"][0]["product_name"], "Widget")
        self.assertEqual(len(data["rep_leaderboard"]), 1)
        self.assertEqual(data["rep_leaderboard"][0]["rep_name"], "Rep One")

    def test_summary_date_range_filter(self):
        data = get_reporting_summary(self.company, date_range="7d")
        self.assertEqual(data["summary"]["confirmed_count"], 1)

    def test_csv_export_does_not_crash(self):
        csv_content = generate_reporting_csv(self.company)
        self.assertIn("Rep One", csv_content)
        self.assertIn("1800.00", csv_content)
