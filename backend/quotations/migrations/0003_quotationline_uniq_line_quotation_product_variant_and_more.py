from django.db import migrations, models


def merge_duplicate_lines(apps, schema_editor):
    """Fold pre-existing duplicate lines into one before the constraints go on.

    Quotes built before the merge rule landed can hold the same (product, variant) on
    several rows. The oldest row wins on price and discount — it carries the original
    add-time snapshot (§5.4) — and the later rows' quantities are added to it.
    """
    QuotationLine = apps.get_model("quotations", "QuotationLine")

    seen = {}
    duplicates = []
    for line in QuotationLine.objects.order_by("created_at", "id"):
        key = (line.quotation_id, line.product_id, line.variant_id)
        if key in seen:
            keeper = seen[key]
            keeper.qty += line.qty
            duplicates.append((keeper, line))
        else:
            seen[key] = line

    for keeper, dupe in duplicates:
        # line_total is recomputed by hand: historical model methods are not available
        # to a migration's frozen model.
        keeper.line_total = (
            keeper.qty * keeper.unit_price * (1 - keeper.discount_pct / 100)
        ).quantize(keeper.line_total)
        keeper.save(update_fields=["qty", "line_total"])
        dupe.delete()


def noop(apps, schema_editor):
    """Irreversible by nature — a merged line cannot be split back into its originals."""


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("quotations", "0002_quotation_max_single_overage"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_lines, noop),
        migrations.AddConstraint(
            model_name="quotationline",
            constraint=models.UniqueConstraint(
                condition=models.Q(("variant__isnull", False)),
                fields=("quotation", "product", "variant"),
                name="uniq_line_quotation_product_variant",
            ),
        ),
        migrations.AddConstraint(
            model_name="quotationline",
            constraint=models.UniqueConstraint(
                condition=models.Q(("variant__isnull", True)),
                fields=("quotation", "product"),
                name="uniq_line_quotation_product_no_variant",
            ),
        ),
    ]
