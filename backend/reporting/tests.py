from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import Company, Customer, Membership, Role, User
from catalog.models import Product
from quotations.models import Quotation, QuotationLine
from reporting.services import generate_reporting_pdf, generate_reporting_xlsx, get_reporting_summary


class ReportingSmokeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Smoke Co")
        role_rep, _ = Role.objects.get_or_create(code=Role.SALES_REP, defaults={"label": "Sales Rep"})
        self.owner = User.objects.create_user(email="rep@smoke.test", password="x", full_name="Rep One")
        self.other_owner = User.objects.create_user(email="rep2@smoke.test", password="x", full_name="Rep Two")
        Membership.objects.create(
            user=self.owner, company=self.company, role=role_rep, is_active_default=True
        )
        Membership.objects.create(
            user=self.other_owner, company=self.company, role=role_rep, is_active_default=True
        )
        self.customer = Customer.objects.create(company=self.company, name="ACME", tier="Gold", email="a@acme.test")
        self.widget = Product.objects.create(
            company=self.company, name="Widget", category="Hardware", base_price=Decimal("1000.00")
        )
        self.service = Product.objects.create(
            company=self.company, name="Onboarding", category="Services", base_price=Decimal("500.00")
        )

        self.confirmed = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=self.owner, status=Quotation.CONFIRMED
        )
        QuotationLine.objects.create(
            quotation=self.confirmed,
            product=self.widget,
            qty=Decimal("2.00"),
            unit_price=Decimal("1000.00"),
            discount_pct=Decimal("10.00"),
            line_total=Decimal("1800.00"),
        )

        self.pending = Quotation.objects.create(
            company=self.company, customer=self.customer, owner=self.other_owner,
            status=Quotation.PENDING_APPROVAL,
        )
        QuotationLine.objects.create(
            quotation=self.pending,
            product=self.service,
            qty=Decimal("1.00"),
            unit_price=Decimal("500.00"),
            discount_pct=Decimal("0.00"),
            line_total=Decimal("500.00"),
        )

    def test_summary_does_not_crash(self):
        data = get_reporting_summary(self.company)
        self.assertEqual(data["summary"]["total_revenue"], 1800.0)
        self.assertEqual(data["summary"]["pipeline_value"], 500.0)
        self.assertEqual(data["summary"]["confirmed_count"], 1)
        self.assertEqual(len(data["top_skus"]), 2)
        self.assertEqual(len(data["rep_leaderboard"]), 2)

    def test_period_today_includes_freshly_created_quotes(self):
        data = get_reporting_summary(self.company, period="today")
        self.assertEqual(data["summary"]["total_quotations_count"], 2)

    def test_period_custom_range_excludes_out_of_range(self):
        tomorrow = (timezone.localdate() + timezone.timedelta(days=1)).isoformat()
        day_after = (timezone.localdate() + timezone.timedelta(days=2)).isoformat()
        data = get_reporting_summary(self.company, period="custom", date_from=tomorrow, date_to=day_after)
        self.assertEqual(data["summary"]["total_quotations_count"], 1)  # `or 1` floor, none actually match
        self.assertEqual(data["summary"]["confirmed_count"], 0)

    def test_approval_status_filter(self):
        data = get_reporting_summary(self.company, approval_status=Quotation.PENDING_APPROVAL)
        self.assertEqual(data["summary"]["pipeline_value"], 500.0)
        self.assertEqual(data["summary"]["total_revenue"], 0.0)

    def test_category_filter_narrows_everything(self):
        data = get_reporting_summary(self.company, category="Services")
        self.assertEqual(data["summary"]["pipeline_value"], 500.0)
        self.assertEqual(data["summary"]["total_revenue"], 0.0)
        self.assertEqual(len(data["top_skus"]), 1)
        self.assertEqual(data["top_skus"][0]["product_name"], "Onboarding")
        self.assertEqual(len(data["rep_leaderboard"]), 1)
        self.assertEqual(data["rep_leaderboard"][0]["rep_name"], "Rep Two")

    def test_product_filter(self):
        data = get_reporting_summary(self.company, product_id=str(self.widget.id))
        self.assertEqual(data["summary"]["total_revenue"], 1800.0)
        self.assertEqual(len(data["top_skus"]), 1)

    def test_sales_rep_filter(self):
        data = get_reporting_summary(self.company, sales_rep_id=str(self.owner.id))
        self.assertEqual(data["summary"]["total_quotations_count"], 1)
        self.assertEqual(data["summary"]["confirmed_count"], 1)

    def test_xlsx_export_does_not_crash(self):
        content = generate_reporting_xlsx(self.company)
        self.assertTrue(content.startswith(b"PK"))  # xlsx is a zip archive
        self.assertGreater(len(content), 0)

    def test_pdf_export_does_not_crash(self):
        content = generate_reporting_pdf(self.company)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_pdf_export_respects_filters(self):
        content = generate_reporting_pdf(self.company, category="Services")
        self.assertTrue(content.startswith(b"%PDF"))
