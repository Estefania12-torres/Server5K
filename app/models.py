from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
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

class Juez(models.Model):
    nombre = models.CharField(max_length=200)
    competencia = models.ForeignKey(
        Competencia, 
        on_delete=models.CASCADE, 
        related_name='jueces'
    )
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombre} - {self.competencia.nombre}"

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

class RegistroTiempo(models.Model):
    id_registro = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    equipo = models.ForeignKey(
        Equipo, 
        on_delete=models.CASCADE, 
        related_name='tiempos'
    )
    
    tiempo = models.BigIntegerField(help_text="Tiempo en milisegundos")
    timestamp = models.DateTimeField(default=timezone.now)
    
    @property
    def juez(self):
        return self.equipo.juez_asignado
    
    @property
    def competencia(self):
        return self.equipo.competencia  
    
    class Meta:
        ordering = ['tiempo']
        indexes = [
            models.Index(fields=['equipo', 'tiempo']),
        ]
        
    def __str__(self):
        return f"Registro {self.id_registro} - Equipo: {self.equipo.nombre} - Tiempo: {self.tiempo} ms"