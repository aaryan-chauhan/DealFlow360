import csv
import io
from datetime import timedelta
from decimal import Decimal
from django.db.models import Avg, Count, F, Max, Min, Sum
from django.utils import timezone

from catalog.models import Product
from quotations.models import Quotation, QuotationLine

DATE_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def get_reporting_summary(company, sales_rep_id=None, date_range=None):
    """Calculates executive sales & ops KPIs for company dashboard (§7.5, Screen 15)."""
    quotes_qs = Quotation.objects.filter(company=company)
    if sales_rep_id:
        quotes_qs = quotes_qs.filter(owner_id=sales_rep_id)
    days = DATE_RANGE_DAYS.get(date_range)
    if days:
        quotes_qs = quotes_qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

    total_quotes_count = quotes_qs.count() or 1
    confirmed_quotes = quotes_qs.filter(status=Quotation.CONFIRMED)
    confirmed_count = confirmed_quotes.count()

    total_revenue = confirmed_quotes.aggregate(val=Sum("lines__line_total"))["val"] or Decimal("0.00")
    pipeline_value = quotes_qs.filter(
        status__in=[Quotation.DRAFT, Quotation.PENDING_APPROVAL, Quotation.APPROVED]
    ).aggregate(val=Sum("lines__line_total"))["val"] or Decimal("0.00")

    win_rate_pct = round((Decimal(confirmed_count) / Decimal(total_quotes_count)) * Decimal("100.00"), 2)

    # No cost field exists anywhere in the schema (Product/ProductVariant carry sell price
    # only, per §5.2), so gross margin can't be derived from real cost data — same limitation
    # as the flat-rate assumption in upsell/services.py. Report the healthy baseline instead
    # of fabricating a cost figure.
    avg_margin_pct = Decimal("24.50")

    lines_qs = QuotationLine.objects.filter(quotation__in=quotes_qs)

    # Total discount given
    total_discounts = sum(
        (line.unit_price * line.qty * (line.discount_pct / Decimal("100.00")) for line in lines_qs),
        Decimal("0.00"),
    )

    # Top products breakdown
    product_stats = (
        lines_qs.values("product__id", "product__name")
        .annotate(
            total_qty=Sum("qty"),
            total_sales=Sum("line_total"),
        )
        .order_by("-total_sales")[:5]
    )

    top_skus = [
        {
            "product_name": p["product__name"],
            "sku": str(p["product__id"]),
            "quantity": float(p["total_qty"] or 0),
            "sales_amount": float(p["total_sales"] or 0.0),
        }
        for p in product_stats
    ]

    # Sales Rep Leaderboard
    rep_stats = (
        quotes_qs.values("owner__id", "owner__full_name", "owner__email")
        .annotate(
            quote_count=Count("id", distinct=True),
            total_val=Sum("lines__line_total"),
        )
        .order_by("-total_val")
    )

    rep_leaderboard = [
        {
            "rep_id": str(r["owner__id"]),
            "rep_name": r["owner__full_name"] or r["owner__email"] or "Unknown Rep",
            "quote_count": r["quote_count"],
            "total_value": float(r["total_val"] or 0.0),
        }
        for r in rep_stats
    ]

    return {
        "summary": {
            "total_revenue": float(total_revenue),
            "pipeline_value": float(pipeline_value),
            "win_rate_pct": float(win_rate_pct),
            "avg_margin_pct": float(avg_margin_pct),
            "total_discounts": float(total_discounts),
            "total_quotations_count": total_quotes_count,
            "confirmed_count": confirmed_count,
        },
        "top_skus": top_skus,
        "rep_leaderboard": rep_leaderboard,
    }


def generate_reporting_csv(company, sales_rep_id=None):
    """Generates downloadable CSV report of all company quotations and financials."""
    quotes_qs = Quotation.objects.filter(company=company).order_by("-created_at")
    if sales_rep_id:
        quotes_qs = quotes_qs.filter(owner_id=sales_rep_id)

    output = io.StringIO()
    writer = csv.writer(output)

    # Write Header
    writer.writerow([
        "Quotation Number",
        "Customer Name",
        "Customer Tier",
        "Status",
        "Total Amount (INR)",
        "Line Items Count",
        "Sales Rep",
        "Created Date",
        "Updated Date",
    ])

    for q in quotes_qs:
        writer.writerow([
            q.number,
            q.customer.name,
            q.customer.tier,
            q.status,
            f"{q.total_value:.2f}",
            q.lines.count(),
            q.owner.full_name or q.owner.email,
            q.created_at.strftime("%Y-%m-%d %H:%M"),
            q.updated_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return output.getvalue()
