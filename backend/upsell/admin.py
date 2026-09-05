from django.contrib import admin

from .models import Suggestion, UpsellRule


@admin.register(UpsellRule)
class UpsellRuleAdmin(admin.ModelAdmin):
    """Cross-sell pairing config (§5.6) — managed here rather than a dedicated
    workspace screen; reps only ever see the suggestions this produces (§7.4),
    never the rule table itself."""

    list_display = [
        "source_product",
        "recommended_product",
        "co_purchase_score",
        "is_promoted",
        "min_margin_pct",
        "company",
    ]
    list_filter = ["is_promoted", "company"]
    search_fields = ["source_product__name", "recommended_product__name"]


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ["quotation", "product", "status", "margin_delta", "created_at"]
    list_filter = ["status"]
