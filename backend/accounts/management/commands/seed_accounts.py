"""Seeds the `accounts` slice of the spec §13 demo data.

Idempotent: re-running matches on email and leaves existing rows (and their passwords)
alone. The catalog / pricing / warehouse / subscription seeds land with their own phases.
"""

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company, Customer, Membership, Role, User

COMPANY_NAME = "Acme Solutions"
DEFAULT_PASSWORD = "DealFlow!2026"

STAFF = [
    ("aaryan@company.com", "Aaryan Chauhan", Role.ADMIN),
    ("neha@company.com", "Neha Sharma", Role.SALES_MANAGER),
    ("priya@company.com", "Priya Nair", Role.FINANCE_OPS),
    ("rohan@company.com", "Rohan Mehta", Role.SALES_REP),
    ("karan@company.com", "Karan Shah", Role.SALES_REP),
]

CUSTOMERS = [
    ("Acme Technologies Pvt Ltd", Customer.GOLD, "procurement@acmetech.example", "Mumbai, India"),
    ("Global Retail Ltd", Customer.SILVER, "buying@globalretail.example", "Delhi, India"),
    ("TechCorp Solutions", Customer.BRONZE, "orders@techcorp.example", "Bangalore, India"),
]


class Command(BaseCommand):
    help = "Seed demo company, internal users with roles, and tiered customers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for newly created accounts (default: {DEFAULT_PASSWORD})",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]

        company, created = Company.objects.get_or_create(name=COMPANY_NAME)
        self.stdout.write(f"{'created' if created else 'reused '}  company   {company.name}")

        roles = {role.code: role for role in Role.objects.all()}
        missing = {code for _, _, code in STAFF} - roles.keys()
        if missing:
            raise SystemExit(f"Roles not seeded: {missing}. Run `manage.py migrate` first.")

        for email, full_name, role_code in STAFF:
            user, created = User.objects.get_or_create(
                email=email, defaults={"full_name": full_name}
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            membership, m_created = Membership.objects.get_or_create(
                user=user,
                company=company,
                defaults={"role": roles[role_code], "is_active_default": True},
            )
            state = "created" if created else "reused "
            note = "" if m_created else "  (membership already existed)"
            self.stdout.write(f"{state}  {membership.role.code:<14} {email}{note}")

        for name, tier, email, location in CUSTOMERS:
            customer, created = Customer.objects.get_or_create(
                company=company,
                email=email,
                defaults={
                    "name": name,
                    "tier": tier,
                    "location": location,
                    # Portal auth (phase 6) reads this; seeded so the flow has something to
                    # authenticate against when `portal_session` arrives.
                    "password_hash": make_password(password),
                },
            )
            if not created and not customer.location:
                customer.location = location
                customer.save(update_fields=["location"])
            self.stdout.write(
                f"{'created' if created else 'reused '}  customer      {customer.name} ({customer.tier})"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. New accounts use the password: {password}"
            )
        )
