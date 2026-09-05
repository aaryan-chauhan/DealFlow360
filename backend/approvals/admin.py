from django.contrib import admin

from .models import ApprovalRequest, ApprovalStep


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ["quotation", "required_level", "risk_score_snapshot", "status", "created_at"]
    list_filter = ["status", "required_level"]
    inlines = [ApprovalStepInline]
