from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Company, Customer, Membership, Role, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "created_at"]
    search_fields = ["name"]


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "is_active", "is_staff", "date_joined"]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["code", "label"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "role", "is_active_default"]
    list_filter = ["role", "company"]
    search_fields = ["user__email", "company__name"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "tier", "email"]
    list_filter = ["tier", "company"]
    search_fields = ["name", "email"]
