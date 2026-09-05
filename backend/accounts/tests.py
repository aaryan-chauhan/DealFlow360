from django.test import TestCase
from rest_framework.test import APIClient

from .models import Company, Customer, Membership, Role, User


class CustomerPortalPasswordTests(TestCase):
    """The optional portal password set from the "Add Customer" form (spec A1) — the
    write-only `password` field on `CustomerSerializer`."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Testco")
        role = Role.objects.get(code=Role.SALES_REP)
        cls.rep = User.objects.create_user(email="rep@test.com", password="x")
        Membership.objects.create(user=cls.rep, company=cls.company, role=role, is_active_default=True)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_creating_a_customer_with_a_password_makes_it_usable(self):
        response = self.client_for(self.rep).post(
            "/api/customers",
            {"name": "Buyer Co", "email": "buy@test.com", "tier": "Gold", "password": "correcthorsebattery"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["has_portal_login"])
        self.assertNotIn("password", response.json())  # write-only, never echoed back

        customer = Customer.objects.get(email="buy@test.com")
        self.assertTrue(customer.check_password("correcthorsebattery"))
        self.assertFalse(customer.check_password("wrong"))

    def test_creating_a_customer_without_a_password_leaves_login_unusable(self):
        response = self.client_for(self.rep).post(
            "/api/customers",
            {"name": "Buyer Co", "email": "buy2@test.com", "tier": "Bronze"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["has_portal_login"])

        customer = Customer.objects.get(email="buy2@test.com")
        self.assertFalse(customer.check_password("anything"))

    def test_updating_without_password_does_not_clear_an_existing_one(self):
        customer = Customer.objects.create(company=self.company, name="Buyer Co", email="buy3@test.com")
        customer.set_password("originalpass")
        customer.save()

        response = self.client_for(self.rep).patch(
            f"/api/customers/{customer.id}", {"location": "Pune"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        customer.refresh_from_db()
        self.assertTrue(customer.check_password("originalpass"))
        self.assertEqual(customer.location, "Pune")

    def test_updating_with_a_new_password_replaces_it(self):
        customer = Customer.objects.create(company=self.company, name="Buyer Co", email="buy4@test.com")
        customer.set_password("originalpass")
        customer.save()

        response = self.client_for(self.rep).patch(
            f"/api/customers/{customer.id}", {"password": "newpassword123"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        customer.refresh_from_db()
        self.assertFalse(customer.check_password("originalpass"))
        self.assertTrue(customer.check_password("newpassword123"))
