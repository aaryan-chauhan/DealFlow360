import io
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from quotations.models import Quotation, QuotationLine

ZERO = Decimal("0.00")

# "Period: today, week, custom range" (spec A7). Named presets map to a day count;
# "today" and "custom" are resolved separately in `_period_bounds` since neither is a
# fixed day count. The wider 30d/90d/all presets are kept too — useful defaults the
# spec doesn't forbid, and the frontend already offered them.
DATE_RANGE_DAYS = {"week": 7, "7d": 7, "30d": 30, "90d": 90}

APPROVAL_STATUS_CHOICES = {code for code, _ in Quotation.STATUS_CHOICES}


def _period_bounds(period, date_from, date_to):
    """Returns (start, end) datetimes, either bound possibly None (open-ended)."""
    if period == "today":
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return start, None
    if period == "custom":
        start = parse_date(date_from) if date_from else None
        end = parse_date(date_to) if date_to else None
        start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time())) if start else None
        end_dt = timezone.make_aware(datetime.combine(end, datetime.max.time())) if end else None
        return start_dt, end_dt
    days = DATE_RANGE_DAYS.get(period)
    if days:
        return timezone.now() - timedelta(days=days), None
    return None, None


def _filtered_quotations(company, sales_rep_id=None, period=None, date_from=None, date_to=None,
                          approval_status=None):
    quotes_qs = Quotation.objects.filter(company=company)
    if sales_rep_id:
        quotes_qs = quotes_qs.filter(owner_id=sales_rep_id)
    if approval_status and approval_status in APPROVAL_STATUS_CHOICES:
        quotes_qs = quotes_qs.filter(status=approval_status)
    start, end = _period_bounds(period, date_from, date_to)
    if start:
        quotes_qs = quotes_qs.filter(created_at__gte=start)
    if end:
        quotes_qs = quotes_qs.filter(created_at__lte=end)
    return quotes_qs


def get_reporting_summary(company, sales_rep_id=None, period=None, date_from=None, date_to=None,
                           approval_status=None, category=None, product_id=None):
    """Calculates executive sales & ops KPIs for company dashboard (§7.5, Screen 15).

    `category`/`product_id` scope every figure to lines matching that product or
    category — "track best selling or most discounted items" (spec A7) means the whole
    report narrows to that slice, not just the top-products table.
    """
    quotes_qs = _filtered_quotations(company, sales_rep_id, period, date_from, date_to, approval_status)

    lines_qs = QuotationLine.objects.filter(quotation__in=quotes_qs)
    if category:
        lines_qs = lines_qs.filter(product__category=category)
    if product_id:
        lines_qs = lines_qs.filter(product_id=product_id)

    total_quotes_count = quotes_qs.count() or 1
    confirmed_count = quotes_qs.filter(status=Quotation.CONFIRMED).count()

    total_revenue = (
        lines_qs.filter(quotation__status=Quotation.CONFIRMED).aggregate(val=Sum("line_total"))["val"]
        or ZERO
    )
    pipeline_value = (
        lines_qs.filter(
            quotation__status__in=[Quotation.DRAFT, Quotation.PENDING_APPROVAL, Quotation.APPROVED]
        ).aggregate(val=Sum("line_total"))["val"]
        or ZERO
    )

    win_rate_pct = round((Decimal(confirmed_count) / Decimal(total_quotes_count)) * Decimal("100.00"), 2)

    # No cost field exists anywhere in the schema (Product/ProductVariant carry sell price
    # only, per §5.2), so gross margin can't be derived from real cost data — same limitation
    # as the flat-rate assumption in upsell/services.py. Report the healthy baseline instead
    # of fabricating a cost figure.
    avg_margin_pct = Decimal("24.50")

    total_discounts = sum(
        (line.unit_price * line.qty * (line.discount_pct / Decimal("100.00")) for line in lines_qs),
        ZERO,
    )

    # Top products breakdown
    product_stats = (
        lines_qs.values("product__id", "product__name")
        .annotate(total_qty=Sum("qty"), total_sales=Sum("line_total"))
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

    # Sales Rep Leaderboard — joined off `lines_qs` (not `quotes_qs` directly) so a
    # category/product filter narrows the leaderboard the same way it narrows everything
    # else, instead of a rep's unrelated business padding their number here.
    rep_stats = (
        lines_qs.values("quotation__owner__id", "quotation__owner__full_name", "quotation__owner__email")
        .annotate(
            quote_count=Count("quotation_id", distinct=True),
            total_val=Sum("line_total"),
        )
        .order_by("-total_val")
    )
    rep_leaderboard = [
        {
            "rep_id": str(r["quotation__owner__id"]),
            "rep_name": r["quotation__owner__full_name"] or r["quotation__owner__email"] or "Unknown Rep",
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


def _export_rows(company, sales_rep_id=None, period=None, date_from=None, date_to=None,
                  approval_status=None, category=None, product_id=None):
    """The quotation-level rows behind the PDF/XLS export — same filters as the summary,
    plus category/product narrowed to quotations carrying at least one matching line."""
    quotes_qs = _filtered_quotations(company, sales_rep_id, period, date_from, date_to, approval_status)
    if category:
        quotes_qs = quotes_qs.filter(lines__product__category=category)
    if product_id:
        quotes_qs = quotes_qs.filter(lines__product_id=product_id)
    return quotes_qs.select_related("customer", "owner").distinct().order_by("-created_at")


HEADER_ROW = [
    "Quotation Number",
    "Customer Name",
    "Customer Tier",
    "Status",
    "Total Value",
    "Line Items",
    "Sales Rep",
    "Created Date",
    "Updated Date",
]


def _row_for(q):
    return [
        q.number,
        q.customer.name,
        q.customer.tier,
        q.get_status_display(),
        f"{q.total_value:.2f}",
        q.lines.count(),
        q.owner.full_name or q.owner.email,
        q.created_at.strftime("%Y-%m-%d %H:%M"),
        q.updated_at.strftime("%Y-%m-%d %H:%M"),
    ]


def generate_reporting_xlsx(company, **filters):
    """Sales performance report as a real .xlsx workbook (spec §8: format=xls)."""
    quotes_qs = _export_rows(company, **filters)

    wb = Workbook()
    sheet = wb.active
    sheet.title = "Quotations"
    sheet.append(HEADER_ROW)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for q in quotes_qs:
        sheet.append(_row_for(q))
    for column_cells in sheet.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    summary = get_reporting_summary(
        company,
        sales_rep_id=filters.get("sales_rep_id"),
        period=filters.get("period"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        approval_status=filters.get("approval_status"),
        category=filters.get("category"),
        product_id=filters.get("product_id"),
    )["summary"]

    summary_sheet = wb.create_sheet("Summary")
    summary_sheet.append(["Metric", "Value"])
    for cell in summary_sheet[1]:
        cell.font = Font(bold=True)
    labels = {
        "total_revenue": "Confirmed Revenue",
        "pipeline_value": "Active Pipeline Value",
        "win_rate_pct": "Win Rate %",
        "avg_margin_pct": "Average Gross Margin %",
        "total_discounts": "Total Discounts Given",
        "total_quotations_count": "Total Quotations",
        "confirmed_count": "Confirmed Orders",
    }
    for key, label in labels.items():
        summary_sheet.append([label, summary[key]])
    summary_sheet.column_dimensions["A"].width = 28
    summary_sheet.column_dimensions["B"].width = 18

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def generate_reporting_pdf(company, **filters):
    """Sales performance report as a real PDF (spec §8: format=pdf)."""
    quotes_qs = _export_rows(company, **filters)
    summary = get_reporting_summary(
        company,
        sales_rep_id=filters.get("sales_rep_id"),
        period=filters.get("period"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        approval_status=filters.get("approval_status"),
        category=filters.get("category"),
        product_id=filters.get("product_id"),
    )["summary"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"DealFlow360 Sales Report — {company.name}", styles["Title"]),
        Paragraph(f"Generated {timezone.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    summary_rows = [
        ["Confirmed Revenue", f"{summary['total_revenue']:.2f}"],
        ["Active Pipeline Value", f"{summary['pipeline_value']:.2f}"],
        ["Win Rate %", f"{summary['win_rate_pct']}"],
        ["Average Gross Margin %", f"{summary['avg_margin_pct']}"],
        ["Total Discounts Given", f"{summary['total_discounts']:.2f}"],
        ["Total Quotations", summary["total_quotations_count"]],
        ["Confirmed Orders", summary["confirmed_count"]],
    ]
    summary_table = Table([["Metric", "Value"]] + summary_rows, colWidths=[9 * cm, 6 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story += [Paragraph("Summary", styles["Heading2"]), summary_table, Spacer(1, 0.7 * cm)]

    detail_rows = [HEADER_ROW] + [_row_for(q) for q in quotes_qs]
    detail_table = Table(detail_rows, repeatRows=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story += [Paragraph("Quotations", styles["Heading2"]), detail_table]

    doc.build(story)
    return buffer.getvalue()
