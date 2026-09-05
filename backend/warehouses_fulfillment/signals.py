"""Auto-opens the fulfillment order when a quotation lands on approved/confirmed (§11).

The listener hangs off `quotation_status_history` rather than `Quotation` itself because
every transition in the system funnels through `Quotation.set_status`, which writes
exactly one history row per change. That means the approval chain, the auto-approve path
and (later) the portal's customer confirmation all trigger this without any of those
modules needing to know fulfillment exists.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from quotations.models import Quotation, QuotationStatusHistory

TRIGGER_STATUSES = {Quotation.APPROVED, Quotation.CONFIRMED}


@receiver(post_save, sender=QuotationStatusHistory, dispatch_uid="open_fulfillment_order")
def open_fulfillment_order(sender, instance, created, **kwargs):
    if not created or instance.to_status not in TRIGGER_STATUSES:
        return

    from .services import ensure_fulfillment_order

    quotation = instance.quotation
    actor = instance.changed_by
    # Deferred to commit so the split is planned against the committed quotation state,
    # and a failure here can never roll back the approval that caused it.
    transaction.on_commit(lambda: ensure_fulfillment_order(quotation, actor))
