from django.contrib import admin

from .models import BillingCycle, ProrationEvent, Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "product", "cycle", "refund_type", "is_active"]
    list_filter = ["company", "cycle", "is_active"]


class BillingCycleInline(admin.TabularInline):
    """Editing `period_start`/`period_end` here is the quickest way to push a demo
    subscription into the middle of its cycle so proration has days to work with."""

    model = BillingCycle
    extra = 0
    fields = ["period_start", "period_end", "amount", "invoice_line"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["product", "customer", "plan", "qty", "status", "next_bill_date"]
    list_filter = ["status", "plan"]
    search_fields = ["customer__name", "product__name"]
    inlines = [BillingCycleInline]


@admin.register(ProrationEvent)
class ProrationEventAdmin(admin.ModelAdmin):
    list_display = ["subscription", "change_type", "delta_amount", "effective_date", "created_at"]
    list_filter = ["change_type"]
    readonly_fields = ["details"]
