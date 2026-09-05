from django.contrib import admin

from .models import Quotation, QuotationLine, QuotationStatusHistory


class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 0
    readonly_fields = ["line_total"]


class StatusHistoryInline(admin.TabularInline):
    model = QuotationStatusHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "changed_by", "changed_at"]
    can_delete = False


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "owner", "status", "blended_risk_score", "updated_at"]
    list_filter = ["status", "company"]
    search_fields = ["number", "customer__name"]
    inlines = [QuotationLineInline, StatusHistoryInline]
