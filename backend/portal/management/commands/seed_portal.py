"""Seeds a live customer-portal link plus an opening message from the rep, so the
negotiation screen has something to show on first load (spec §13).

Not idempotent in the usual sense, and it cannot be: only a SHA-256 of the token is
stored, so an existing link's URL can never be recovered. Re-running therefore revokes
whatever link is outstanding and prints a fresh one — which is also exactly what the
"re-send the link" button does in the workspace.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Company
from approvals.services import route_quotation
from portal.models import NegotiationMessage
from portal.services import issue_session, portal_url
from pricing_discounts.services import assess_quotation
from quotations.models import Quotation

COMPANY_NAME = "Acme Solutions"
DEFAULT_FRONTEND = "http://localhost:5173"

# Prefer a quote the customer can actually act on. `pending_approval` is deliberately last:
# the portal would open, but every button would be disabled while internal review runs.
# A `draft` sits mid-list because it is one `route_quotation` call away from shareable —
# but only when its current terms already clear policy (see `pick_quotation`).
STATUS_PREFERENCE = [
    Quotation.NEGOTIATION,
    Quotation.APPROVED,
    Quotation.DRAFT,
    Quotation.PENDING_APPROVAL,
]

OPENING_MESSAGE = (
    "Hi — I've put the quotation together as we discussed. Everything on it is priced at "
    "our current rates and it's valid until the date shown above. Have a look through, and "
    "if the numbers need to move, send me a counter-offer here rather than by email so it "
    "goes straight through our approval desk."
)


class Command(BaseCommand):
    help = "Seed an active portal session (and an opening rep message) for testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quotation",
            help="Quotation number (e.g. Q-2026-009). Defaults to the best candidate found.",
        )
        parser.add_argument(
            "--base-url",
            default=DEFAULT_FRONTEND,
            help=f"Frontend origin used to build the printed link (default: {DEFAULT_FRONTEND})",
        )

    def pick_quotation(self, company, number):
        if number:
            try:
                return Quotation.objects.get(company=company, number=number)
            except Quotation.DoesNotExist:
                raise SystemExit(f"Quotation '{number}' not found in {company.name}.")

        candidates = [
            q
            for q in Quotation.objects.filter(company=company, status__in=STATUS_PREFERENCE)
            .select_related("customer")
            .prefetch_related("lines__product")
            if q.lines.exists()
            # A draft is only a candidate if it would auto-approve on submission. Picking
            # one that routes for review would hand back a portal link whose every button
            # is disabled — the opposite of "testable immediately".
            and (q.status != Quotation.DRAFT or not assess_quotation(q).needs_approval)
        ]
        if not candidates:
            raise SystemExit(
                "No shareable quotation with lines was found. Run `seed_quotations` first."
            )
        # Line count dominates the ranking: a quote spanning two product categories is the
        # only kind that actually demonstrates per-category ceilings during a counter-offer
        # (a Gold customer capped at 15% overall but 10% on Services).
        candidates.sort(
            key=lambda q: (-q.lines.count(), STATUS_PREFERENCE.index(q.status), q.number)
        )
        return candidates[0]

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(name=COMPANY_NAME)
        except Company.DoesNotExist:
            raise SystemExit(f"Company '{COMPANY_NAME}' not found. Run `seed_accounts` first.")

        quotation = self.pick_quotation(company, options["quotation"])

        if quotation.status == Quotation.DRAFT:
            # Route rather than force the status: the quote goes through the same engine a
            # rep's own submission does, so the seeded deal carries a real cached risk
            # score and a real status-history row instead of a hand-set field.
            route_quotation(quotation, quotation.owner, trigger="seed_portal")
            quotation.refresh_from_db()
            self.stdout.write(
                f"routed   {quotation.number}  draft -> {quotation.status} "
                "(within policy, so no approval was needed)"
            )

        # An empty thread on first load makes the screen look broken rather than new.
        opener, created = NegotiationMessage.objects.get_or_create(
            quotation=quotation,
            author_user=quotation.owner,
            message_type=NegotiationMessage.COMMENT,
            defaults={"body": OPENING_MESSAGE},
        )
        self.stdout.write(
            f"{'created' if created else 'reused '}  message   from "
            f"{quotation.owner.full_name or quotation.owner.email}"
        )

        session, raw_token = issue_session(quotation, quotation.owner)
        self.stdout.write("created  session   (any earlier link for this quote is now revoked)")

        ceilings = ", ".join(
            f"{line.product.name} [{line.product.category}] @ {line.discount_pct}%"
            for line in quotation.lines.select_related("product")
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Portal link ready"))
        self.stdout.write(f"  quotation  {quotation.number}  ({quotation.status})")
        self.stdout.write(f"  customer   {quotation.customer.name} ({quotation.customer.tier} tier)")
        self.stdout.write(f"  owner      {quotation.owner.full_name or quotation.owner.email}")
        self.stdout.write(f"  lines      {ceilings}")
        self.stdout.write(f"  expires    {session.expires_at:%Y-%m-%d %H:%M %Z}")
        self.stdout.write("")
        self.stdout.write("  Open this in a private / incognito window:")
        self.stdout.write(f"  {portal_url(raw_token, options['base_url'])}")
        self.stdout.write("")
        self.stdout.write(f"  Raw token (for curl):\n  {raw_token}")
