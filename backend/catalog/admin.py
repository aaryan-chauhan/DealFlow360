from django.contrib import admin

from .models import PriceList, PriceListItem, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "base_price", "is_subscription", "is_active", "company"]
    list_filter = ["category", "is_subscription", "is_active", "company"]
    search_fields = ["name"]
    inlines = [ProductVariantInline]


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ["name", "currency", "company"]


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ["product", "price_list", "tier", "price_rule", "price"]
    list_filter = ["tier", "price_rule", "price_list"]
