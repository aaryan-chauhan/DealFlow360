from django.contrib import admin

from .models import ApprovalChainRule, CategoryDiscountCeiling, DiscountTier


class CategoryCeilingInline(admin.TabularInline):
    model = CategoryDiscountCeiling
    extra = 0


@admin.register(DiscountTier)
class DiscountTierAdmin(admin.ModelAdmin):
    list_display = ["name", "max_discount_pct", "company"]
    inlines = [CategoryCeilingInline]


@admin.register(ApprovalChainRule)
class ApprovalChainRuleAdmin(admin.ModelAdmin):
    list_display = ["discount_range_from", "discount_range_to", "required_level", "company"]
    list_filter = ["required_level"]
