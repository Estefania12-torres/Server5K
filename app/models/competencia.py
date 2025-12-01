from django.db import models
from django.utils import timezone


class Competencia(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    datetime = models.DateTimeField(verbose_name="Fecha y hora")

    is_active = models.BooleanField(default=True, verbose_name="Activa")
    is_running = models.BooleanField(default=False, verbose_name="En curso")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de inicio")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de finalización")

    class Meta:
        verbose_name = "Competencia"
        verbose_name_plural = "Competencias"

    def __str__(self):
        return self.name

    def start(self):
        """Inicia la competencia solo si no hay otra en curso"""
        if self.is_running:
            return {'success': False, 'message': 'already_running'}
        
        # Verificar si hay otra competencia en curso
        otra_en_curso = Competencia.objects.filter(is_running=True).exclude(id=self.id).first()
        if otra_en_curso:
            return {
                'success': False, 
                'message': 'another_running',
                'competencia': otra_en_curso
            }
        
        # Iniciar esta competencia
        self.is_running = True
        self.started_at = timezone.now()
        self.save()
        
        # Notificar por WebSocket usando el servicio
        from app.services.competencia_service import CompetenciaService
        service = CompetenciaService()
        service._notificar_jueces_competencia(
            competencia_id=self.id,
            tipo='competencia_iniciada',
            mensaje='La competencia ha iniciado',
            competencia_nombre=self.name,
            en_curso=True,
            started_at=self.started_at.isoformat() if self.started_at else None
        )
        
        return {'success': True, 'message': 'started', 'competencia': self}

    def stop(self):
        """Detiene la competencia"""
        if not self.is_running:
            return {'success': False, 'message': 'not_running'}
        
        self.is_running = False
        self.finished_at = timezone.now()
        self.save()
        
        # Notificar por WebSocket usando el servicio
        from app.services.competencia_service import CompetenciaService
        service = CompetenciaService()
        service._notificar_jueces_competencia(
            competencia_id=self.id,
            tipo='competencia_detenida',
            mensaje='La competencia ha finalizado',
            competencia_nombre=self.name,
            en_curso=False,
            finished_at=self.finished_at.isoformat() if self.finished_at else None
        )
        
        return {'success': True, 'message': 'stopped', 'competencia': self}

    def get_status_code(self):
        """Retorna el código de estado de la competencia"""
        if self.is_running:
            return 'running'
        elif self.finished_at:
            return 'finished'
        return 'scheduled'

    def get_status_display(self):
        """Retorna el texto descriptivo del estado"""
        estados = {
            'running': 'En Curso',
            'finished': 'Finalizada',
            'scheduled': 'Programada',
        }
        return estados.get(self.get_status_code(), 'Desconocido')
