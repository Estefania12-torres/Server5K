from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
import uuid

CATEGORIA_CHOICES = [
    ('estudiantes', 'Estudiantes por Equipos'),
    ('interfacultades', 'Interfacultades por Equipos'),
]

class Competencia(models.Model):
    nombre = models.CharField(max_length=200)
    fecha_hora = models.DateTimeField()
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES
    )
    activa = models.BooleanField(default=True)
    en_curso = models.BooleanField(default=False, verbose_name="En curso")
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de finalización")
    
    def iniciar_competencia(self):
        """Inicia la competencia"""
        if not self.en_curso:
            self.en_curso = True
            self.fecha_inicio = timezone.now()
            self.save()
            return True
        return False
    
    def detener_competencia(self):
        """Detiene la competencia"""
        if self.en_curso:
            self.en_curso = False
            self.fecha_fin = timezone.now()
            self.save()
            return True
        return False
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Competencia"
        verbose_name_plural = "Competencias"
        
    def get_estado_display(self):
        """Retorna el estado actual de la competencia"""
        if self.en_curso:
            return 'en_curso'
        elif self.fecha_fin:
            return 'finalizada'
        else:
            return 'programada'
    
    def get_estado_texto(self):
        """Retorna el texto del estado para mostrar"""
        estado = self.get_estado_display()
        estados = {
            'en_curso': 'En Curso',
            'finalizada': 'Finalizada',
            'programada': 'Programada'
        }
        return estados.get(estado, 'Desconocido')

class Juez(models.Model):
    # Credenciales de autenticación
    username = models.CharField(max_length=150, unique=True, verbose_name="Usuario")
    password = models.CharField(max_length=128, verbose_name="Contraseña")
    
    # Información personal
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Apellido")
    email = models.EmailField(blank=True, verbose_name="Email")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    
    # Relación con competencia
    competencia = models.ForeignKey(
        Competencia, 
        on_delete=models.CASCADE, 
        related_name='jueces',
        verbose_name="Competencia"
    )
    
    # Estado
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    last_login = models.DateTimeField(null=True, blank=True, verbose_name="Último login")
    
    class Meta:
        verbose_name = "Juez"
        verbose_name_plural = "Jueces"
    
    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} - {self.competencia.nombre}"
        return f"{self.username} - {self.competencia.nombre}"
    
    def get_full_name(self):
        """Retorna el nombre completo del juez"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def set_password(self, raw_password):
        """Establece la contraseña hasheada"""
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Verifica la contraseña"""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)
    
    @property
    def is_authenticated(self):
        """Siempre retorna True para compatibilidad con JWT"""
        return True

class Equipo(models.Model):
    nombre = models.CharField(max_length=200)
    dorsal = models.IntegerField()
    
    juez_asignado = models.ForeignKey(
        Juez,
        on_delete=models.CASCADE,
        related_name='equipos_asignados'
    )
    
    @property
    def competencia(self):
        return self.juez_asignado.competencia
    
    class Meta:
        unique_together = ('juez_asignado', 'dorsal')
        ordering = ['dorsal']
    
    def __str__(self):
        return f"{self.nombre} (Dorsal {self.dorsal})"
    
    def tiempo_total(self):
        """Retorna el tiempo total acumulado de todos los registros en milisegundos"""
        from django.db.models import Sum
        total = self.tiempos.aggregate(total=Sum('tiempo'))['total']
        return total or 0

    def tiempo_promedio(self):
        """Retorna el tiempo promedio de todos los registros en milisegundos"""
        from django.db.models import Avg
        promedio = self.tiempos.aggregate(promedio=Avg('tiempo'))['promedio']
        return int(promedio) if promedio else 0

    def mejor_tiempo(self):
        """Retorna el mejor tiempo (más bajo) del equipo"""
        return self.tiempos.order_by('tiempo').first()

    def tiempo_total_formateado(self):
        """Retorna el tiempo total en formato legible"""
        total_ms = self.tiempo_total()
        ms = total_ms % 1000
        total_seconds = total_ms // 1000
        s = total_seconds % 60
        total_minutes = total_seconds // 60
        m = total_minutes % 60
        h = total_minutes // 60
        return f"{h}h {m}m {s}s {ms}ms"

    def numero_registros(self):
        """Retorna el número total de registros de tiempo"""
        return self.tiempos.count()

class RegistroTiempo(models.Model):
    id_registro = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    equipo = models.ForeignKey(
        Equipo, 
        on_delete=models.CASCADE, 
        related_name='tiempos'
    )
    
    # Relación directa con competencia para evitar datos inconsistentes
    competencia = models.ForeignKey(
        Competencia,
        on_delete=models.CASCADE,
        related_name='registros_tiempo',
        verbose_name="Competencia"
    )
    
    # Keep a single integer field for total milliseconds (used for ordering/search)
    tiempo = models.BigIntegerField(help_text="Tiempo en milisegundos")

    # New, more granular fields
    horas = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    minutos = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(59)])
    segundos = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(59)])
    milisegundos = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(999)])

    timestamp = models.DateTimeField(default=timezone.now)
    
    @property
    def juez(self):
        return self.equipo.juez_asignado
    
    class Meta:
        ordering = ['tiempo']
        indexes = [
            models.Index(fields=['equipo', 'tiempo']),
        ]
        
    def __str__(self):
        return f"Registro {self.id_registro} - Equipo: {self.equipo.nombre} - Tiempo: {self.tiempo} ms"

    def save(self, *args, **kwargs):
        """
        Keep `tiempo` (total milliseconds) consistent with the granular fields.

        - If any of the granular fields are non-zero, compute `tiempo` from them.
        - Otherwise, if all granular fields are zero and `tiempo` is present, derive the granular
          fields from `tiempo` so existing records are preserved.
        - Auto-assign competencia from equipo if not provided.
        """
        # Auto-asignar competencia desde el equipo si no está presente
        if not self.competencia_id:
            self.competencia = self.equipo.competencia
        
        try:
            any_component = any([self.horas, self.minutos, self.segundos, self.milisegundos])
        except Exception:
            # In migrations or when fields aren't available yet, defer to default save
            return super().save(*args, **kwargs)

        if any_component:
            total_ms = ((int(self.horas) * 3600 + int(self.minutos) * 60 + int(self.segundos)) * 1000) + int(self.milisegundos)
            self.tiempo = int(total_ms)
        else:
            # derive components from existing tiempo
            total = int(self.tiempo or 0)
            ms = total % 1000
            total_seconds = total // 1000
            s = total_seconds % 60
            total_minutes = total_seconds // 60
            m = total_minutes % 60
            h = total_minutes // 60
            self.horas = h
            self.minutos = m
            self.segundos = s
            self.milisegundos = ms

        return super().save(*args, **kwargs)