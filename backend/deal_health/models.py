from django.db import models
from accounts.models import Company, TimeStampedModel, UUIDModel
from quotations.models import Quotation


class AnomalyAlert(UUIDModel, TimeStampedModel):
    """Deal Health Anomaly Alert (spec §7.3, Screen 14).
    
    Tracks flagged deal risks across 3 categories:
    - stalled_deal: Quotes in Draft/Pending state unchanged for > 5 days.
    - discount_anomaly: Quotes with overall discount exceeding baseline/tier allowance.
    - delivery_slippage: Orders facing backorders or promised date slippage.
    """

    STALLED_DEAL = "stalled_deal"
    DISCOUNT_ANOMALY = "discount_anomaly"
    DELIVERY_SLIPPAGE = "delivery_slippage"
    ALERT_TYPE_CHOICES = [
        (STALLED_DEAL, "Stalled Deal (>5 days inactive)"),
        (DISCOUNT_ANOMALY, "Discount Anomaly (>Rep Baseline)"),
        (DELIVERY_SLIPPAGE, "Delivery Slippage Risk"),
    ]

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    SEVERITY_CHOICES = [
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (CRITICAL, "Critical"),
    ]

    OPEN = "Open"
    ESCALATED = "Escalated"
    NUDGED = "Nudged"
    RESOLVED = "Resolved"
    STATUS_CHOICES = [
        (OPEN, "Open"),
        (ESCALATED, "Escalated"),
        (NUDGED, "Nudged"),
        (RESOLVED, "Resolved"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="anomaly_alerts")
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="anomaly_alerts", null=True, blank=True
    )
    alert_type = models.CharField(max_length=32, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    recommended_action = models.CharField(max_length=255, blank=True)
    nudge_count = models.PositiveIntegerField(default=0)
    last_nudged_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_by_name = models.CharField(max_length=128, blank=True)
    escalation_note = models.TextField(blank=True)

    class Meta:
        db_table = "anomaly_alert"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.title} ({self.status})"
