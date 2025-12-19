"""
Comando para generar datos de la competencia UNL 5K ACTIVATE 2025.

Uso en desarrollo (con Docker):
docker compose exec web python manage.py populate_unl5k_2025

Uso en producción (con Docker):
docker compose exec web python manage.py populate_unl5k_2025 --production

Opciones:
--clear         Elimina todos los datos existentes antes de crear nuevos
--production    Genera contraseñas seguras (para producción real)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string
import string
import os

from app.models import Competencia, Juez, Equipo


class Command(BaseCommand):
    help = 'Genera datos para UNL 5K ACTIVATE 2025: competencia, 72 jueces y equipos'

    # Datos de jueces reales del documento
    JUECES_DATOS = [
        (1, "Alejandro Ramiro"),
        (2, "Calderón Gabriel"),
        (3, "Chiribiga Steven"),
        (4, "Cueva Daly"),
        (5, "Izquierdo Yoder"),
        (6, "Jerves Kadens"),
        (7, "Jimenez Juan"),
        (8, "Lima Diego"),
        (9, "Macanchi Solange"),
        (10, "Murillo Alex"),
        (11, "Leon Isai"),
        (12, "Ovaco Edisson"),
        (13, "Rosado Saul"),
        (14, "Sarmiento Edwin"),
        (15, "Seraquive Andersson"),
        (16, "Torres Bayron"),
        (17, "Torres Jhoel"),
        (18, "Valdez Joseph"),
        (19, "Vera Brayan"),
        (20, "Vallego Paul"),
        (21, "Armijos Juan"),
        (22, "Bentancourt Ana"),
        (23, "Calva Marlin"),
        (24, "Carrion Franz"),
        (25, "Encarnacion Jhon"),
        (26, "Guaillas Jhostin"),
        (27, "Hernandes Andry"),
        (28, "Jimenez Joseth"),
        (29, "Negran Daniel"),
        (30, "Palacios Edison"),
        (31, "Pardo Tifany"),
        (32, "Pardo Terresa"),
        (33, "Rojas Nataly"),
        (34, "Rueda Jerson"),
        (35, "Sarango Maria"),
        (36, "Sarango Junior"),
        (37, "Sarango Shandy"),
        (38, "Silverio Jairo"),
        (39, "Valdez Darlin"),
        (40, "Vargas Wilson"),
        (41, "Vargas Alejandro"),
        (42, "Guachizaca Danny"),
        (43, "Pachar Orlando"),
        (44, "Burgos Manuel"),
        (45, "Carrion Jostin"),
        (46, "Macas Bryan"),
        (47, "Cajas ignacio"),
        (48, "Ajila Jefferson"),
        (49, "Torre Katerine"),
        (50, "Robles Yulissa"),
        (51, "Jumbo Fabricio"),
        (52, "Erreyes Pablo"),
        (53, "Barba Maria"),
        (54, "Tinitana Adrian"),
        (55, "Rodrigrez Alex"),
        (56, "Seas Jacson"),
        (57, "Medina Jonathan"),
        (58, "Balcazar Diego"),
        (59, "Simancos Jorge"),
        (60, "Jimenez Josselyn"),
        (61, "Pinos Liliana"),
        (62, "Naranjo Elvis"),
        (63, "Ortiz Marisol"),
        (64, "Jimenez Emanuel"),
        (65, "Yunga Cristhian"),
        (66, "Contento Anghelo"),
        (67, "Vivanco Steven"),
        (68, "Bravo Jenner"),
        (69, "Ordoñez Fabricio"),
        (70, "Alvarez Axel"),
        (71, "Huanca Mauro"),
        (72, "Ordoñez Saul"),
    ]

    # Datos de equipos reales del documento con categorías
    # (número_equipo, nombre_equipo, categoría)
    EQUIPOS_DATOS = [
        (1, "Capyras", "interfacultades"),
        (2, "Agropecuaría", "interfacultades"),
        (3, "Team Educativa", "interfacultades"),
        (4, "Energia A", "interfacultades"),
        (5, "Energia B", "interfacultades"),
        (6, "Jurídica", "interfacultades"),
        (7, "Salud", "interfacultades"),
        (8, "Sindicato de Trabajador UNL", "interfacultades"),
        (9, "Los Mejías", "interfacultades"),
        (10, "Los Mejías 2", "interfacultades"),
        (11, "Sexto \"A\"", "estudiantes"),
        (12, "Segundo \"B\"", "estudiantes"),
        (13, "Odonto Runners", "estudiantes"),
        (14, "Los estratos perdidos", "estudiantes"),
        (15, "Titanes del esmalte", "estudiantes"),
        (16, "Odontorunners", "estudiantes"),
        (17, "Los duros de la política", "estudiantes"),
        (18, "Atletas UNL", "estudiantes"),
        (19, "Los caso cerrado", "estudiantes"),
        (20, "Laboratorio clínico", "estudiantes"),
        (21, "Gram positivos", "estudiantes"),
        (22, "Gram variables", "estudiantes"),
        (23, "Laboratorio clínico", "estudiantes"),
        (24, "Equipo Alfa", "estudiantes"),
        (25, "Educación Especial 3ro", "estudiantes"),
        (26, "Educación Especial 7mo", "estudiantes"),
        (27, "Los discípulos de Bailón", "estudiantes"),
        (28, "Educación básica", "estudiantes"),
        (29, "Educación básica", "estudiantes"),
        (30, "Neuro UNL", "estudiantes"),
        (31, "Psico Runners", "estudiantes"),
        (32, "Vital Force", "estudiantes"),
        (33, "Pulso en marcha", "estudiantes"),
        (34, "Ingeniería automotriz", "estudiantes"),
        (35, "Agrivolt 2.0", "estudiantes"),
        (36, "Agrivolt 1.0", "estudiantes"),
        (37, "Team Fenix", "estudiantes"),
        (38, "Administración de empresas", "estudiantes"),
        (39, "Educación Inicial \"B\"", "estudiantes"),
        (40, "Educación Inicial \"A\"", "estudiantes"),
        (41, "Computación \"C\"", "estudiantes"),
        (42, "Los Hp", "estudiantes"),
        (43, "Computación \"B\"", "estudiantes"),
        (44, "Computación \"A\"", "estudiantes"),
        (45, "Segundo-Octavo\"A\"", "estudiantes"),
        (46, "Sexto \"A\" grupo \"B\"", "estudiantes"),
        (47, "Los deo cuadrado", "estudiantes"),
        (48, "Los brokers del 5k", "estudiantes"),
        (49, "PINE", "estudiantes"),
        (50, "Comunicación", "estudiantes"),
        (51, "Los vinculadores", "estudiantes"),
        (52, "Hospital veterinario", "estudiantes"),
        (53, "Foxy y sus chavales", "estudiantes"),
        (54, "Los más unidos", "estudiantes"),
        (55, "Administradores públicos", "estudiantes"),
        (56, "Los simplex's", "estudiantes"),
        (57, "Artes músicales", "estudiantes"),
        (58, "Derecho", "estudiantes"),
        (59, "Química y Biología", "estudiantes"),
        (60, "Educación especial", "estudiantes"),
        (61, "Biología y Química", "estudiantes"),
        (62, "Pollitos", "estudiantes"),
        (63, "Computación D", "estudiantes"),
        (64, "Informática", "estudiantes"),
        (65, "Matemática y Física \"A\"", "estudiantes"),
        (66, "Matemática y Física \"B\"", "estudiantes"),
        (67, "Las craks", "estudiantes"),
        (68, "Medicina", "estudiantes"),
        (69, "Agrorunners", "estudiantes"),
        (70, "Sexto \"B\" Contabilidad 1", "estudiantes"),
        (71, "Sexto \"B\" Contabilidad 2", "estudiantes"),
        (72, "Dos que tres", "estudiantes"),
    ]

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

    def generate_secure_password(self, length=12):
        """Genera una contraseña segura para producción."""
        chars = string.ascii_letters + string.digits + '!@#$%&*'
        return get_random_string(length, chars)

    def handle(self, *args, **options):
        is_production = options['production']

        # Mostrar modo
        if is_production:
            self.stdout.write(self.style.WARNING('='*70))
            self.stdout.write(self.style.WARNING(' MODO PRODUCCIÓN - Contraseñas seguras'))
            self.stdout.write(self.style.WARNING('='*70))
        else:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS(' MODO DESARROLLO - Contraseñas: juezN123'))
            self.stdout.write(self.style.SUCCESS('='*70))

        # Limpiar datos si se solicita
        if options['clear']:
            self.stdout.write(self.style.WARNING('\nEliminando datos existentes...'))
            Equipo.objects.all().delete()
            Juez.objects.all().delete()
            Competencia.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Datos eliminados correctamente'))

        # Crear competencia
        self.stdout.write('\nCreando competencia...')
        competencia = Competencia.objects.create(
            name="UNL 5K ACTIVATE 2025",
            datetime=timezone.datetime(2025, 12, 18, 8, 0, tzinfo=timezone.get_current_timezone()),
            is_active=True,
            is_running=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Competencia creada: {competencia.name}'))
        self.stdout.write(f'  Fecha: {competencia.datetime.strftime("%d/%m/%Y %H:%M")}')

        # Crear jueces y equipos
        self.stdout.write(f'\nCreando 72 jueces y equipos...')
        credenciales = []

        for (j_id, full_name), (numero_equipo, nombre_equipo, categoria) in zip(
            self.JUECES_DATOS, self.EQUIPOS_DATOS
        ):
            # Dividir nombre completo en nombre y apellido
            parts = full_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            # Generar credenciales
            username = f"juez{j_id}"
            if is_production:
                password = self.generate_secure_password(12)
            else:
                password = f"juez{j_id}123"

            # Crear juez
            juez = Juez.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=f"{username}@5k.local",
                is_active=True
            )
            juez.set_password(password)
            juez.save()

            # Crear equipo (usando numero_equipo en el campo number)
            equipo = Equipo.objects.create(
                name=nombre_equipo,
                number=numero_equipo,
                category=categoria,
                competition=competencia,
                judge=juez
            )

            # Guardar credenciales
            credenciales.append({
                'numero_juez': j_id,
                'numero_equipo': numero_equipo,
                'username': username,
                'password': password,
                'nombre': first_name,
                'apellido': last_name,
                'equipo': nombre_equipo,
                'categoria': categoria,
            })

            self.stdout.write(
                f'  ✓ Juez {j_id:2d}/{len(self.JUECES_DATOS)}: '
                f'@{username:8s} → Equipo #{numero_equipo:2d}: {nombre_equipo:30s}'
            )

        # Generar archivo de credenciales
        credenciales_path = os.path.join(os.getcwd(), 'credenciales_unl5k_2025.txt')
        with open(credenciales_path, 'w', encoding='utf-8') as f:
            f.write('═'*70 + '\n')
            f.write('       CREDENCIALES DE ACCESO - UNL 5K ACTIVATE 2025\n')
            f.write('═'*70 + '\n')
            f.write(f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}\n')
            f.write(f'Competencia: {competencia.name}\n')
            f.write(f'Fecha evento: {competencia.datetime.strftime("%d/%m/%Y %H:%M")}\n')
            f.write(f'Modo: {"PRODUCCIÓN" if is_production else "DESARROLLO"}\n')
            f.write('═'*70 + '\n\n')

            # Agrupar por categoría
            interfacultades = [c for c in credenciales if c['categoria'] == 'interfacultades']
            estudiantes = [c for c in credenciales if c['categoria'] == 'estudiantes']

            # Interfacultades
            f.write('┌' + '─'*68 + '┐\n')
            f.write('│' + ' INTERFACULTADES POR EQUIPOS (10 equipos)'.center(68) + '│\n')
            f.write('└' + '─'*68 + '┘\n\n')

            for cred in interfacultades:
                f.write(f"JUEZ #{cred['numero_juez']:02d} - {cred['nombre']} {cred['apellido']}\n")
                f.write(f"  Usuario:    {cred['username']}\n")
                f.write(f"  Contraseña: {cred['password']}\n")
                f.write(f"  Email:      {cred['username']}@5k.local\n")
                f.write(f"  Equipo:     #{cred['numero_equipo']:02d} - {cred['equipo']}\n")
                f.write('─'*70 + '\n')

            # Estudiantes
            f.write('\n┌' + '─'*68 + '┐\n')
            f.write('│' + ' ESTUDIANTES POR EQUIPOS (62 equipos)'.center(68) + '│\n')
            f.write('└' + '─'*68 + '┘\n\n')

            for cred in estudiantes:
                f.write(f"JUEZ #{cred['numero_juez']:02d} - {cred['nombre']} {cred['apellido']}\n")
                f.write(f"  Usuario:    {cred['username']}\n")
                f.write(f"  Contraseña: {cred['password']}\n")
                f.write(f"  Email:      {cred['username']}@5k.local\n")
                f.write(f"  Equipo:     #{cred['numero_equipo']:02d} - {cred['equipo']}\n")
                f.write('─'*70 + '\n')

            f.write('\n' + '═'*70 + '\n')
            if is_production:
                f.write('IMPORTANTE: Guarda este archivo en un lugar seguro.\n')
                f.write('    Estas contraseñas son únicas y no se pueden recuperar.\n')
            else:
                f.write('NOTA: Estas credenciales son para desarrollo/pruebas.\n')
                f.write('    Patrón de contraseñas: juezN123 (ej: juez1123, juez2123...)\n')
                f.write('    Use --production para generar contraseñas seguras.\n')
            f.write('═'*70 + '\n')

        # Resumen final
        self.stdout.write(self.style.SUCCESS('\n' + '═'*70))
        self.stdout.write(self.style.SUCCESS('           RESUMEN - UNL 5K ACTIVATE 2025'))
        self.stdout.write(self.style.SUCCESS('═'*70))
        self.stdout.write(f'  Competencia: {competencia.name}')
        self.stdout.write(f'  Fecha evento: {competencia.datetime.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'  Total Jueces: {Juez.objects.count()}')
        self.stdout.write(f'  Total Equipos: {Equipo.objects.count()}')
        self.stdout.write(f'    • Interfacultades: {Equipo.objects.filter(category="interfacultades").count()}')
        self.stdout.write(f'    • Estudiantes: {Equipo.objects.filter(category="estudiantes").count()}')
        self.stdout.write(f'  Modo: {"PRODUCCIÓN" if is_production else "DESARROLLO"}')
        self.stdout.write(self.style.SUCCESS('═'*70))

        self.stdout.write(self.style.WARNING(f'\nCredenciales guardadas en: {credenciales_path}'))

        if is_production:
            self.stdout.write(self.style.ERROR('\nIMPORTANTE: Guarda el archivo de credenciales en un lugar seguro'))
            self.stdout.write(self.style.ERROR('    Las contraseñas son aleatorias y no se pueden recuperar.'))
        else:
            self.stdout.write('\nEjemplo de acceso:')
            self.stdout.write(f'    Usuario: juez1')
            self.stdout.write(f'    Contraseña: juez1123')
            self.stdout.write(f'    Equipo asignado: #01 - Capyras')

        self.stdout.write(self.style.SUCCESS('\nDatos generados exitosamente.'))
        self.stdout.write(self.style.SUCCESS('  El sistema está listo para UNL 5K ACTIVATE 2025\n'))