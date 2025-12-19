"""
Comando para generar datos iniciales del sistema.

Uso en desarrollo (con Docker):
    docker compose exec web python manage.py populate_data

Uso en producción (con Docker):
    docker compose exec web python manage.py populate_data --production --jueces 20

Opciones:
    --clear             Elimina todos los datos existentes antes de crear nuevos
    --production        Genera contraseñas seguras (para producción real)
    --jueces N          Número de jueces/equipos a crear (default: 50)
    --competencia NAME  Nombre de la competencia (default: auto-generado)
    --password PASS     Contraseña base para todos los jueces (solo desarrollo)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string
import random
import os
import string
from app.models import Competencia, Juez, Equipo


class Command(BaseCommand):
    help = 'Genera datos iniciales: competencia, jueces y equipos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Elimina todos los datos existentes antes de crear nuevos',
        )
        parser.add_argument(
            '--production',
            action='store_true',
            help='Modo producción: genera contraseñas seguras aleatorias',
        )
        parser.add_argument(
            '--jueces',
            type=int,
            default=50,
            help='Número de jueces/equipos a crear (default: 50)',
        )
        parser.add_argument(
            '--competencia',
            type=str,
            default=None,
            help='Nombre de la competencia (default: auto-generado)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Contraseña base para todos los jueces en desarrollo (ej: --password mipass genera mipass1, mipass2...)',
        )

    def generate_secure_password(self, length=12):
        """Genera una contraseña segura para producción."""
        chars = string.ascii_letters + string.digits + '!@#$%&*'
        return get_random_string(length, chars)

    def handle(self, *args, **options):
        is_production = options['production']
        num_jueces = options['jueces']
        nombre_competencia = options['competencia']
        password_base = options['password']
        
        # Validar número de jueces
        if num_jueces < 1 or num_jueces > 100:
            self.stdout.write(self.style.ERROR('El número de jueces debe estar entre 1 y 100'))
            return
        
        # Mostrar modo
        if is_production:
            self.stdout.write(self.style.WARNING('='*60))
            self.stdout.write(self.style.WARNING('  MODO PRODUCCIÓN - Contraseñas seguras'))
            self.stdout.write(self.style.WARNING('='*60))
        else:
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('  MODO DESARROLLO - Contraseñas simples'))
            self.stdout.write(self.style.SUCCESS('='*60))
        
        if options['clear']:
            self.stdout.write(self.style.WARNING('\nEliminando datos existentes...'))
            Equipo.objects.all().delete()
            Juez.objects.all().delete()
            Competencia.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Datos eliminados correctamente'))
        
        # Crear competencia
        self.stdout.write('\nCreando competencia...')
        if nombre_competencia:
            comp_name = nombre_competencia
        else:
            comp_name = f"Carrera 5K UNL {timezone.now().year}"
        
        competencia = Competencia.objects.create(
            name=comp_name,
            datetime=timezone.now() + timezone.timedelta(days=7),
            is_active=True,
            is_running=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Competencia creada: {competencia.name}'))
        
        # Lista de nombres de equipos
        nombres_equipos = [
            'Los Veloces', 'Corredores Unidos', 'Team Thunder', 'Atletas Elite', 'Racing Crew',
            'Speed Masters', 'Los Invencibles', 'Running Stars', 'Team Phoenix', 'Campeones 5K',
            'Relámpagos FC', 'Halcones Rápidos', 'Águilas Corredoras', 'Titanes del Asfalto', 'Fénix Runners',
            'Centauros Veloces', 'Los Imparables', 'Gacelas Urbanas', 'Team Rocket', 'Sprint Kings',
            'Maratonistas Pro', 'Runners Elite', 'Los Meteoros', 'Flash Team', 'Tornado Runners',
            'Los Gladiadores', 'Panteras Negras', 'Team Pegasus', 'Los Campeones', 'Ultra Runners',
            'Los Guerreros', 'Team Infinity', 'Correcaminos FC', 'Los Titanes', 'Águilas Doradas',
            'Team Vortex', 'Los Dragones', 'Rayos del Norte', 'Storm Runners', 'Los Vikingos',
            'Team Alpha', 'Los Spartanos', 'Jaguar Racing', 'Team Omega', 'Los Leones',
            'Cobra Team', 'Los Pumas', 'Tiger Runners', 'Team Delta', 'Los Halcones',
            'Team Sigma', 'Los Cóndores', 'Puma Racing', 'Team Bravo', 'Los Jaguares',
            'Falcon Team', 'Los Tigres', 'Eagle Runners', 'Team Charlie', 'Los Lobos',
            'Wolf Pack', 'Los Osos', 'Bear Team', 'Team Echo', 'Los Toros',
            'Bull Runners', 'Los Delfines', 'Dolphin Team', 'Team Foxtrot', 'Los Tiburones',
            'Shark Racing', 'Los Búfalos', 'Buffalo Team', 'Team Golf', 'Los Venados',
            'Deer Runners', 'Los Caballos', 'Horse Team', 'Team Hotel', 'Los Leopardos',
            'Leopard Racing', 'Los Linces', 'Lynx Team', 'Team India', 'Los Coyotes',
            'Coyote Runners', 'Los Zorros', 'Fox Team', 'Team Juliet', 'Los Cuervos',
            'Raven Racing', 'Los Gavilanes', 'Hawk Team', 'Team Kilo', 'Los Bisontes',
            'Bison Runners', 'Los Alces', 'Moose Team', 'Team Lima', 'Los Castores',
        ]
        
        # Crear jueces y equipos
        self.stdout.write(f'\nCreando {num_jueces} jueces y equipos...')
        credenciales = []
        
        for i in range(1, num_jueces + 1):
            username = f"juez{i}"
            
            # Generar contraseña
            if is_production:
                password = self.generate_secure_password(12)
            elif password_base:
                password = f"{password_base}{i}"
            else:
                password = f"juez{i}123"
            
            # Crear juez
            juez = Juez.objects.create(
                username=username,
                first_name=f"Juez",
                last_name=f"#{i}",
                email=f"juez{i}@5k.local",
                is_active=True
            )
            juez.set_password(password)
            juez.save()
            
            # Crear equipo
            nombre_equipo = nombres_equipos[i-1] if i <= len(nombres_equipos) else f"Equipo {i}"
            dorsal = i * 10
            
            equipo = Equipo.objects.create(
                name=nombre_equipo,
                number=dorsal,
                category=random.choice(['estudiantes', 'interfacultades']),
                competition=competencia,
                judge=juez
            )
            
            credenciales.append({
                'numero': i,
                'username': username,
                'password': password,
                'equipo': nombre_equipo,
                'dorsal': dorsal,
            })
            
            self.stdout.write(f'  ✓ Juez {i}/{num_jueces}: @{username} → Equipo: {nombre_equipo} (Dorsal {dorsal})')
        
        # Generar archivo de credenciales
        credenciales_path = os.path.join(os.getcwd(), 'credenciales_jueces.txt')
        
        with open(credenciales_path, 'w', encoding='utf-8') as f:
            f.write('═'*70 + '\n')
            f.write('CREDENCIALES DE ACCESO - SISTEMA 5K\n')
            f.write('═'*70 + '\n')
            f.write(f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}\n')
            f.write(f'Competencia: {competencia.name}\n')
            f.write(f'Modo: {"PRODUCCIÓN" if is_production else "DESARROLLO"}\n')
            f.write('═'*70 + '\n\n')
            
            for cred in credenciales:
                f.write(f"JUEZ #{cred['numero']:02d}\n")
                f.write(f"  Usuario: {cred['username']}\n")
                f.write(f"  Contraseña: {cred['password']}\n")
                f.write(f"  Equipo: {cred['equipo']} (Dorsal {cred['dorsal']})\n")
                f.write('─'*70 + '\n')
            
            f.write('\n' + '═'*70 + '\n')
            if is_production:
                f.write('IMPORTANTE: Guarda este archivo en un lugar seguro.\n')
                f.write('    Estas contraseñas son únicas y no se pueden recuperar.\n')
            else:
                f.write('NOTA: Estas credenciales son para desarrollo/pruebas.\n')
                f.write('    Use --production para generar contraseñas seguras.\n')
            f.write('═'*70 + '\n')
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n' + '═'*60))
        self.stdout.write(self.style.SUCCESS('  RESUMEN DE DATOS GENERADOS'))
        self.stdout.write(self.style.SUCCESS('═'*60))
        self.stdout.write(f'  Competencia: {competencia.name}')
        self.stdout.write(f'  Fecha programada: {competencia.datetime.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'  Total Jueces: {Juez.objects.count()}')
        self.stdout.write(f'  Total Equipos: {Equipo.objects.count()}')
        self.stdout.write(f'  Modo: {"PRODUCCIÓN" if is_production else "DESARROLLO"}')
        self.stdout.write(self.style.SUCCESS('═'*60))
        
        self.stdout.write(self.style.WARNING(f'\nCredenciales guardadas en: {credenciales_path}'))
        
        if is_production:
            self.stdout.write(self.style.ERROR('\nIMPORTANTE: Guarda el archivo de credenciales en un lugar seguro'))
            self.stdout.write(self.style.ERROR('    Las contraseñas son aleatorias y no se pueden recuperar.'))
        else:
            self.stdout.write('\nEjemplo de acceso:')
            self.stdout.write(f'   Usuario: juez1')
            self.stdout.write(f'   Contraseña: {credenciales[0]["password"]}')
        
        self.stdout.write(self.style.SUCCESS('\nDatos generados exitosamente.'))
