"""Provisions billing artefacts when a quotation is won (§11).

Hangs off `quotation_status_history` for the same reason the fulfillment listener does:
every transition funnels through `Quotation.set_status`, which writes exactly one history
row per change, so the approval chain, the auto-approve path and (later) the portal's
customer confirmation all trigger provisioning without any of them knowing that
subscriptions or invoices exist.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from quotations.models import Quotation, QuotationStatusHistory

TRIGGER_STATUSES = {Quotation.APPROVED, Quotation.CONFIRMED}


@receiver(post_save, sender=QuotationStatusHistory, dispatch_uid="provision_billing_for_quotation")
def provision_billing(sender, instance, created, **kwargs):
    if not created or instance.to_status not in TRIGGER_STATUSES:
        return

    from .services import provision_quotation

    quotation = instance.quotation
    actor = instance.changed_by
    # Deferred to commit so the invoice is built from committed quotation state, and a
    # failure here can never roll back the approval that caused it. `provision_quotation`
    # is idempotent, so approved -> confirmed firing twice raises only one invoice.
    transaction.on_commit(lambda: provision_quotation(quotation, actor))
