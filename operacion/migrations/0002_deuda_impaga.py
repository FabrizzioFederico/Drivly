from datetime import timedelta

from django.db import migrations, models
from django.db.models import F


def calcular_vence_bloqueo(apps, schema_editor):
    apps.get_model("operacion", "Deuda").objects.update(vence_bloqueo=F("egreso_real") + timedelta(hours=72))


class Migration(migrations.Migration):

    dependencies = [
        ("operacion", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="deuda",
            name="monto_condonado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="deuda",
            name="motivo_condonacion",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="deuda",
            name="recordatorios_enviados",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="deuda",
            name="estado",
            field=models.CharField(
                choices=[("PENDIENTE", "Pendiente"), ("PAGADA", "Pagada"), ("CONDONADA", "Condonada"),
                         ("INCOBRABLE", "Incobrable")],
                default="PENDIENTE", max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="deuda",
            name="vence_bloqueo",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(calcular_vence_bloqueo, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="deuda",
            name="vence_bloqueo",
            field=models.DateTimeField(),
        ),
    ]
