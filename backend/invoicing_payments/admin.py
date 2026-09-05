from django.contrib import admin

from .models import CreditNote, Invoice, InvoiceLine, Payment


class InvoiceLineInline(admin.TabularInline):
    """`product` and `subscription` are shown side by side on purpose: a line must have
    exactly one of them filled in, and a DB constraint rejects any row that sets both."""

    model = InvoiceLine
    extra = 0
    fields = ["description", "product", "subscription", "qty", "unit_price", "amount"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "customer",
        "invoice_type",
        "status",
        "issue_date",
        "total_amount",
    ]
    list_filter = ["invoice_type", "status"]
    search_fields = ["invoice_number", "customer__name"]
    inlines = [InvoiceLineInline, PaymentInline]


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ["customer", "amount", "invoice", "subscription", "issued_at"]
    search_fields = ["customer__name", "reason"]
