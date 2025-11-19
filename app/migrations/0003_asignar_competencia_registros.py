# Generated manually - Data migration

from django.db import migrations


def asignar_competencia_a_registros(apps, schema_editor):
    """Asigna la competencia a los registros existentes basándose en el equipo"""
    RegistroTiempo = apps.get_model('app', 'RegistroTiempo')
    
    registros_sin_competencia = RegistroTiempo.objects.filter(competencia__isnull=True)
    
    for registro in registros_sin_competencia:
        # Obtener la competencia desde equipo -> juez -> competencia
        if registro.equipo and registro.equipo.juez_asignado:
            registro.competencia = registro.equipo.juez_asignado.competencia
            registro.save(update_fields=['competencia'])
    
    print(f"✓ Se asignó competencia a {registros_sin_competencia.count()} registros")


def revertir_asignacion(apps, schema_editor):
    """Revertir la asignación poniendo competencia en NULL"""
    RegistroTiempo = apps.get_model('app', 'RegistroTiempo')
    RegistroTiempo.objects.all().update(competencia=None)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_registrotiempo_competencia'),
    ]

    operations = [
        migrations.RunPython(asignar_competencia_a_registros, revertir_asignacion),
    ]
