from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company
from catalog.models import Product
from upsell.models import UpsellRule

COMPANY_NAME = "Acme Solutions"


class Command(BaseCommand):
    help = "Seeds cross-sell pairing rules (e.g. Hardware -> Extended Warranty)."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Company '{COMPANY_NAME}' not found. Run seed_accounts first."))
            return

        products = {p.name: p for p in Product.objects.filter(company=company)}
        dell = products.get("Dell Latitude 5440")
        m365 = products.get("Microsoft 365 Business")
        warranty = products.get("Extended Warranty")
        onsite = products.get("Onsite Support Plan")
        training = products.get("Training & Onboarding")
        hp_elitebook = products.get("HP EliteBook 840")

        rules_to_seed = []
        if dell and warranty:
            rules_to_seed.append({
                "source": dell,
                "target": warranty,
                "score": Decimal("85.00"),
                "promoted": True,
                "min_margin": Decimal("10.00"),
            })
        if dell and onsite:
            rules_to_seed.append({
                "source": dell,
                "target": onsite,
                "score": Decimal("75.00"),
                "promoted": False,
                "min_margin": Decimal("12.00"),
            })
        if m365 and training:
            rules_to_seed.append({
                "source": m365,
                "target": training,
                "score": Decimal("90.00"),
                "promoted": True,
                "min_margin": Decimal("15.00"),
            })
        if hp_elitebook and warranty:
            rules_to_seed.append({
                "source": hp_elitebook,
                "target": warranty,
                "score": Decimal("80.00"),
                "promoted": True,
                "min_margin": Decimal("10.00"),
            })
        if hp_elitebook and onsite:
            rules_to_seed.append({
                "source": hp_elitebook,
                "target": onsite,
                "score": Decimal("70.00"),
                "promoted": False,
                "min_margin": Decimal("12.00"),
            })

        for r in rules_to_seed:
            rule, created = UpsellRule.objects.get_or_create(
                company=company,
                source_product=r["source"],
                recommended_product=r["target"],
                defaults={
                    "co_purchase_score": r["score"],
                    "is_promoted": r["promoted"],
                    "min_margin_pct": r["min_margin"],
                },
            )
            verb = "created" if created else "reused "
            self.stdout.write(
                f"{verb}  upsell rule   {r['source'].name} -> {r['target'].name} "
                f"(score: {r['score']}, promoted: {r['promoted']})"
            )

        self.stdout.write(self.style.SUCCESS("Done. Upsell rules seeded."))
