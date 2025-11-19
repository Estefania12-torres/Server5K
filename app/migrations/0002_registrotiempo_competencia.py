# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrotiempo',
            name='competencia',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='registros_tiempo',
                to='app.competencia',
                verbose_name='Competencia',
                null=True  # Temporal para datos existentes
            ),
        ),
    ]
