from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
from app.models import Competencia, Juez, Equipo

class Command(BaseCommand):
    help = 'Genera datos de prueba: 1 competencia, 10 jueces y equipos usando Faker'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Elimina todos los datos existentes antes de crear nuevos',
        )

    def handle(self, *args, **options):
        fake = Faker('es_ES')  # Usar locale español
        
        if options['clear']:
            self.stdout.write(self.style.WARNING('Eliminando datos existentes...'))
            Equipo.objects.all().delete()
            Juez.objects.all().delete()
            Competencia.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Datos eliminados correctamente'))
        
        # Crear una competencia
        self.stdout.write('Creando competencia...')
        competencia = Competencia.objects.create(
            nombre=f"5K {fake.city()} {timezone.now().year}",
            fecha_hora=fake.date_time_between(start_date='now', end_date='+30d', tzinfo=timezone.get_current_timezone()),
            categoria=random.choice(['estudiantes', 'interfacultades']),
            activa=True,
            en_curso=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Competencia creada: {competencia.nombre}'))
        
        # Crear 10 jueces
        self.stdout.write('\nCreando 10 jueces...')
        jueces_creados = []
        
        for i in range(1, 11):
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"juez{i}"
            
            juez = Juez.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=fake.email(),
                telefono=fake.phone_number()[:20],
                competencia=competencia,
                activo=True
            )
            
            # Establecer contraseña
            juez.set_password(f"juez{i}123")  # Contraseña simple para desarrollo
            juez.save()
            
            jueces_creados.append(juez)
            self.stdout.write(self.style.SUCCESS(f'  ✓ Juez {i}/10: {juez.get_full_name()} (@{username})'))
        
        # Crear equipos (1 equipo por juez)
        self.stdout.write('\nCreando equipos...')
        nombres_equipos = [
            'Los Veloces', 'Corredores Unidos', 'Team Thunder',
            'Atletas Elite', 'Racing Crew', 'Speed Masters',
            'Los Invencibles', 'Running Stars', 'Team Phoenix',
            'Campeones 5K'
        ]
        
        for i, juez in enumerate(jueces_creados, start=1):
            nombre_equipo = nombres_equipos[i-1]
            dorsal = i * 10  # Dorsales: 10, 20, 30, etc.
            
            equipo = Equipo.objects.create(
                nombre=nombre_equipo,
                dorsal=dorsal,
                juez_asignado=juez
            )
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Equipo {i}/10: {equipo.nombre} (Dorsal {dorsal}) - Juez: {juez.get_full_name()}'))
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS GENERADOS'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'Competencia: {competencia.nombre}')
        self.stdout.write(f'Categoría: {competencia.get_categoria_display()}')
        self.stdout.write(f'Fecha: {competencia.fecha_hora.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'Total de Jueces: {Juez.objects.filter(competencia=competencia).count()}')
        self.stdout.write(f'Total de Equipos: {Equipo.objects.filter(juez_asignado__competencia=competencia).count()}')
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Datos generados exitosamente!'))
        self.stdout.write(self.style.WARNING('\nCredenciales de acceso:'))
        self.stdout.write('  Usuario: juez1, juez2, ..., juez10')
        self.stdout.write('  Contraseña: juez1123, juez2123, ..., juez10123')
