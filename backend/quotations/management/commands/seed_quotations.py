"""Seeds demo quotations across reps and customers, including deliberately
over-ceiling lines so approval routing can be exercised end to end. Idempotent."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company, Customer, User
from approvals.services import route_quotation
from catalog.models import Product
from quotations.models import Quotation, QuotationLine

COMPANY_NAME = "Acme Solutions"

# owner email, customer name, submit?, [(product, qty, discount_pct)]
QUOTATIONS = [
    (
        "rohan@company.com",
        "Acme Technologies Pvt Ltd",  # Gold, tier cap 15%
        False,
        [("Dell Latitude 5440", 10, "10.00"), ("Extended Warranty", 10, "5.00")],
        "Draft, everything inside policy.",
    ),
    (
        "rohan@company.com",
        "Global Retail Ltd",  # Silver, tier cap 10%
        True,
        [("Microsoft 365 Business", 20, "18.00"), ("Dell Latitude 5440", 5, "5.00")],
        "Software line 8 pts over its 10% ceiling -> Sales Manager.",
    ),
    (
        "karan@company.com",
        "TechCorp Solutions",  # Bronze, tier cap 5%
        True,
        [("Extended Warranty", 10, "25.00"), ("Training & Onboarding", 2, "5.00")],
        "Services line 20 pts over the 5% Bronze cap -> Sales Manager + Finance.",
    ),
    (
        "karan@company.com",
        "Acme Technologies Pvt Ltd",
        False,
        [("Onsite Support Plan", 12, "12.00")],
        "Draft with a Services line 2 pts over - not submitted yet.",
    ),
]


class Command(BaseCommand):
    help = "Seed draft and pending-approval quotations, routing the submitted ones."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first.")

        if not Product.objects.filter(company=company).exists():
            raise SystemExit("No products found. Run `seed_catalog` and `seed_pricing` first.")

        for owner_email, customer_name, submit, lines, note in QUOTATIONS:
            owner = User.objects.get(email=owner_email)
            customer = Customer.objects.get(company=company, name=customer_name)

            existing = Quotation.objects.filter(
                company=company, owner=owner, customer=customer
            ).first()
            if existing:
                self.stdout.write(f"reused   {existing.number}  ({existing.status})")
                continue

            quotation = Quotation.objects.create(
                company=company, customer=customer, owner=owner
            )
            for product_name, qty, discount in lines:
                product = Product.objects.get(company=company, name=product_name)
                QuotationLine.objects.create(
                    quotation=quotation,
                    product=product,
                    qty=Decimal(qty),
                    unit_price=product.base_price,
                    discount_pct=Decimal(discount),
                    line_type=(
                        QuotationLine.RECURRING
                        if product.is_subscription
                        else QuotationLine.ONE_TIME
                    ),
                )

            if submit:
                assessment, request = route_quotation(quotation, owner)
                quotation.refresh_from_db()
                routed = request.required_level if request else "no approval needed"
                self.stdout.write(
                    f"created  {quotation.number}  {owner.full_name} / {customer.name} "
                    f"({customer.tier})  score {assessment.routing_score} -> {routed}"
                )
            else:
                self.stdout.write(
                    f"created  {quotation.number}  {owner.full_name} / {customer.name} "
                    f"({customer.tier})  draft"
                )
            self.stdout.write(f"         {note}")

        self.stdout.write(self.style.SUCCESS("\nDone."))
