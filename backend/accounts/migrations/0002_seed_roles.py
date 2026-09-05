from django.db import migrations

ROLES = [
    ("sales_rep", "Sales Rep"),
    ("sales_manager", "Sales Manager"),
    ("finance_ops", "Finance / Ops"),
    ("admin", "Admin"),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, label in ROLES:
        Role.objects.get_or_create(code=code, defaults={"label": label})


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code__in=[code for code, _ in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(seed_roles, unseed_roles)]
