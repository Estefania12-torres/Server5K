from django.db import models

CATEGORIA_CHOICES = [
    ('estudiantes', 'Estudiantes por Equipos'),
    ('interfacultades', 'Interfacultades por Equipos'),
]


class Equipo(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    number = models.PositiveIntegerField(verbose_name="Dorsal")
    category = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='estudiantes',
        verbose_name="Categoría",
    )

    competition = models.ForeignKey(
        'Competencia',
        on_delete=models.CASCADE,
        related_name='teams',
        verbose_name='Competencia',
    )

    judge = models.ForeignKey(
        'Juez',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teams',
        verbose_name='Juez asignado',
    )

    class Meta:
        unique_together = ('competition', 'number')
        ordering = ['number']
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"

    def __str__(self):
        return f"{self.name} (Dorsal {self.number})"

    def total_time(self):
        """Retorna el tiempo total en milisegundos"""
        from django.db.models import Sum
        total = self.times.aggregate(total=Sum('time'))['total']
        return total or 0

    def average_time(self):
        """Retorna el tiempo promedio en milisegundos"""
        from django.db.models import Avg
        promedio = self.times.aggregate(promedio=Avg('time'))['promedio']
        return int(promedio) if promedio else 0

    def best_time(self):
        """Retorna el mejor registro de tiempo"""
        return self.times.order_by('time').first()

    def formatted_total_time(self):
        """Retorna el tiempo total formateado"""
        total_ms = self.total_time()
        ms = total_ms % 1000
        total_seconds = total_ms // 1000
        s = total_seconds % 60
        total_minutes = total_seconds // 60
        m = total_minutes % 60
        h = total_minutes // 60
        return f"{h}h {m}m {s}s {ms}ms"

    def records_count(self):
        """Retorna el número de registros"""
        return self.times.count()


class ResultadoEquipo(Equipo):
    class Meta:
        proxy = True
        verbose_name = 'Resultado por Equipo'
        verbose_name_plural = '📊 Resultados por Equipo'
