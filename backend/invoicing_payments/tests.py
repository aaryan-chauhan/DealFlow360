"""HTTP-level regression tests for invoicing/payments (§5.10, §7.3.3-4).

No test file existed for this app before — every endpoint here was previously verified
only by manual code reading, the same blind spot that let the reporting PDF-export bug
ship. These go through APIClient against the real URLs, not the service layer directly.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Company, Customer, Membership, Role, User
from catalog.models import Product
from quotations.models import Quotation

from .models import Invoice, InvoiceLine

D = Decimal


class InvoicingTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Testco")
        roles = {r.code: r for r in Role.objects.all()}

        def member(email, role_code):
            user = User.objects.create_user(email=email, password="x")
            Membership.objects.create(
                user=user, company=cls.company, role=roles[role_code], is_active_default=True
            )
            return user

        cls.rep = member("rep@t.example", Role.SALES_REP)
        cls.finance = member("fin@t.example", Role.FINANCE_OPS)
        cls.admin = member("admin@t.example", Role.ADMIN)

        cls.customer = Customer.objects.create(
            company=cls.company, name="Buyer Ltd", tier=Customer.BRONZE, email="b@t.example"
        )
        cls.widget = Product.objects.create(
            company=cls.company, name="Widget", category=Product.HARDWARE, base_price=D("100.00")
        )

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _invoice(self, total="1000.00"):
        # Linked to a rep-owned quotation so the rep-scoping rule (scope_to_owner via
        # quotation__owner) makes the invoice visible to the rep for read/403 checks,
        # rather than 404ing them out of the queryset entirely.
        quotation = Quotation.objects.create(
            company=self.company, number="Q-TEST-1", customer=self.customer, owner=self.rep
        )
        invoice = Invoice.objects.create(
            customer=self.customer, quotation=quotation, invoice_type=Invoice.ONE_TIME
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            product=self.widget,
            description="Widget x10",
            qty=D("10.00"),
            unit_price=D("100.00"),
            amount=D(total),
        )
        invoice.recompute_total()
        invoice.recompute_status()
        return invoice


class RecordPaymentTests(InvoicingTestBase):
    def test_finance_can_record_payment(self):
        invoice = self._invoice()
        resp = self._client(self.finance).post(
            f"/api/invoices/{invoice.id}/record-payment",
            {"amount": "400.00", "method": "bank_transfer"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "partially_paid")
        self.assertEqual(Decimal(resp.data["amount_paid"]), D("400.00"))

    def test_sales_rep_cannot_record_payment(self):
        invoice = self._invoice()
        resp = self._client(self.rep).post(
            f"/api/invoices/{invoice.id}/record-payment", {"amount": "100.00"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_payment_cannot_exceed_balance_due(self):
        invoice = self._invoice()
        resp = self._client(self.finance).post(
            f"/api/invoices/{invoice.id}/record-payment", {"amount": "5000.00"}
        )
        self.assertEqual(resp.status_code, 400)


class IssueCreditNoteTests(InvoicingTestBase):
    def test_finance_can_issue_credit_note(self):
        invoice = self._invoice()
        resp = self._client(self.finance).post(
            f"/api/invoices/{invoice.id}/issue-credit-note",
            {"amount": "250.00", "reason": "Damaged on arrival"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["credit_notes"]), 1)
        self.assertEqual(Decimal(resp.data["amount_credited"]), D("250.00"))
        self.assertEqual(Decimal(resp.data["balance_due"]), D("750.00"))

    def test_admin_can_issue_credit_note(self):
        invoice = self._invoice()
        resp = self._client(self.admin).post(
            f"/api/invoices/{invoice.id}/issue-credit-note",
            {"amount": "100.00", "reason": "Goodwill adjustment"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_sales_rep_cannot_issue_credit_note(self):
        invoice = self._invoice()
        resp = self._client(self.rep).post(
            f"/api/invoices/{invoice.id}/issue-credit-note",
            {"amount": "100.00", "reason": "Trying anyway"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_credit_note_cannot_exceed_balance_due(self):
        invoice = self._invoice()
        resp = self._client(self.finance).post(
            f"/api/invoices/{invoice.id}/issue-credit-note",
            {"amount": "5000.00", "reason": "Too much"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_credit_note_blocked_on_void_invoice(self):
        invoice = self._invoice()
        invoice.status = Invoice.VOID
        invoice.save(update_fields=["status"])
        resp = self._client(self.finance).post(
            f"/api/invoices/{invoice.id}/issue-credit-note",
            {"amount": "10.00", "reason": "Should not apply"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_can_issue_credit_note_flag_reflects_role(self):
        invoice = self._invoice()
        resp = self._client(self.finance).get(f"/api/invoices/{invoice.id}")
        self.assertTrue(resp.data["can_issue_credit_note"])
        resp = self._client(self.rep).get(f"/api/invoices/{invoice.id}")
        self.assertFalse(resp.data["can_issue_credit_note"])
