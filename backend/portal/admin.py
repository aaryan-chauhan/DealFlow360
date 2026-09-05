from django.contrib import admin

from .models import NegotiationMessage, PortalSession


@admin.register(PortalSession)
class PortalSessionAdmin(admin.ModelAdmin):
    list_display = ("quotation", "customer", "expires_at", "last_used_at", "revoked_at")
    list_filter = ("expires_at",)
    search_fields = ("quotation__number", "customer__name")
    # The hash is the credential's shadow; nothing here should invite editing it by hand.
    readonly_fields = ("token_hash", "last_used_at", "created_at", "updated_at")


@admin.register(NegotiationMessage)
class NegotiationMessageAdmin(admin.ModelAdmin):
    list_display = ("quotation", "message_type", "author_name", "counter_discount_pct", "created_at")
    list_filter = ("message_type",)
    search_fields = ("quotation__number", "body")
