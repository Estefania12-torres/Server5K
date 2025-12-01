from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
import os
from app.models import Competencia, Juez, Equipo

class Command(BaseCommand):
    help = 'Genera datos de prueba: 1 competencia, 16 jueces y equipos usando Faker'

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
            name=f"5K {fake.city()} {timezone.now().year}",
            datetime=fake.date_time_between(start_date='now', end_date='+30d', tzinfo=timezone.get_current_timezone()),
            is_active=True,
            is_running=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Competencia creada: {competencia.name}'))
        
        # Crear 16 jueces
        self.stdout.write('\nCreando 16 jueces...')
        jueces_creados = []
        credenciales = []  # Lista para guardar credenciales
        
        for i in range(1, 17):
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"juez{i}"
            
            juez = Juez.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=fake.email(),
                is_active=True
            )
            
            # Establecer contraseña
            password = f"juez{i}123"  # Contraseña simple para desarrollo
            juez.set_password(password)
            juez.save()
            
            # Guardar credenciales
            credenciales.append({
                'numero': i,
                'username': username,
                'email': juez.email,
                'password': password,
                'nombre_completo': juez.get_full_name()
            })
            
            jueces_creados.append(juez)
            self.stdout.write(self.style.SUCCESS(f'  ✓ Juez {i}/16: {juez.get_full_name()} (@{username})'))
        
        # Crear equipos (1 equipo por juez)
        self.stdout.write('\nCreando equipos...')
        nombres_equipos = [
            'Los Veloces', 'Corredores Unidos', 'Team Thunder',
            'Atletas Elite', 'Racing Crew', 'Speed Masters',
            'Los Invencibles', 'Running Stars', 'Team Phoenix',
            'Campeones 5K', 'Relámpagos FC', 'Halcones Rápidos',
            'Águilas Corredoras', 'Titanes del Asfalto', 'Fénix Runners',
            'Centauros Veloces'
        ]
        
        for i, juez in enumerate(jueces_creados, start=1):
            nombre_equipo = nombres_equipos[i-1]
            dorsal = i * 10  # Dorsales: 10, 20, 30, etc.
            
            equipo = Equipo.objects.create(
                name=nombre_equipo,
                number=dorsal,
                category=random.choice(['estudiantes', 'interfacultades']),
                competition=competencia,
                judge=juez
            )
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Equipo {i}/16: {equipo.name} (Dorsal {dorsal}) - Juez: {juez.get_full_name()}'))
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS GENERADOS'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'Competencia: {competencia.name}')
        self.stdout.write(f'Fecha: {competencia.datetime.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'Total de Jueces: {Juez.objects.count()}')
        self.stdout.write(f'Total de Equipos: {Equipo.objects.filter(competition=competencia).count()}')
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Generar archivo con credenciales
        self.stdout.write('\nGenerando archivo de credenciales...')
        credenciales_path = os.path.join(os.getcwd(), 'credenciales_jueces.txt')
        
        with open(credenciales_path, 'w', encoding='utf-8') as f:
            f.write('='*70 + '\n')
            f.write('CREDENCIALES DE ACCESO - SISTEMA 5K\n')
            f.write(f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}\n')
            f.write(f'Competencia: {competencia.name}\n')
            f.write('='*70 + '\n\n')
            
            for cred in credenciales:
                f.write(f"JUEZ #{cred['numero']:02d}\n")
                f.write(f"  Nombre: {cred['nombre_completo']}\n")
                f.write(f"  Usuario: {cred['username']}\n")
                f.write(f"  Email: {cred['email']}\n")
                f.write(f"  Contraseña: {cred['password']}\n")
                f.write('-'*70 + '\n\n')
            
            f.write('='*70 + '\n')
            f.write('NOTA: Estas credenciales son solo para desarrollo/pruebas.\n')
            f.write('En producción, use contraseñas seguras y únicas.\n')
            f.write('='*70 + '\n')
        
        self.stdout.write(self.style.SUCCESS(f'✓ Archivo de credenciales generado: {credenciales_path}'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Datos generados exitosamente!'))
        self.stdout.write(self.style.WARNING('\nCredenciales de acceso guardadas en: credenciales_jueces.txt'))
        self.stdout.write('  Usuario: juez1, juez2, ..., juez16')
        self.stdout.write('  Contraseña: juez1123, juez2123, ..., juez16123')
