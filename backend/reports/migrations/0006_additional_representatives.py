# Generated manually

from django.db import migrations, models


def migrate_expert_to_json(apps, schema_editor):
    EnvironmentalReport = apps.get_model("reports", "EnvironmentalReport")
    for r in EnvironmentalReport.objects.all():
        pos = (getattr(r, "expert_position", None) or "").strip()
        name = (getattr(r, "expert_full_name", None) or "").strip()
        if pos or name:
            r.additional_unit_representatives = [{"position": pos, "full_name": name}]
            r.save(update_fields=["additional_unit_representatives"])


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0005_add_expert_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="environmentalreport",
            name="additional_unit_representatives",
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name="Додаткові представники підрозділу (посада, ПІБ)",
            ),
        ),
        migrations.RunPython(migrate_expert_to_json, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="environmentalreport",
            name="expert_position",
        ),
        migrations.RemoveField(
            model_name="environmentalreport",
            name="expert_full_name",
        ),
    ]
