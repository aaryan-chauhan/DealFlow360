from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from accounts.models import Company, UUIDModel


class AuditEntry(UUIDModel):
    """One universal, append-only log using a generic FK so it can attach to *any* table —
    an approval, a discount edit, a subscription cancellation — without a separate audit
    table per module (§5.13). Rows are never edited or deleted (§14).
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="audit_entries")
    user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="audit_entries"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    target = GenericForeignKey("content_type", "object_id")
    action = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_entry"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.action} by {self.user_id} at {self.created_at}"

    def save(self, *args, **kwargs):
        if self.pk and AuditEntry.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit entries are append-only and cannot be modified.")
        return super().save(*args, **kwargs)


def record(company, user, target, action, reason="", **metadata):
    """The single entry point for writing audit rows — keeps callers from hand-rolling
    content types and makes every write consistent (user + timestamp + reason)."""
    return AuditEntry.objects.create(
        company=company,
        user=user if getattr(user, "is_authenticated", False) else None,
        content_type=ContentType.objects.get_for_model(target.__class__),
        object_id=target.pk,
        action=action,
        reason=reason or "",
        metadata=metadata,
    )
