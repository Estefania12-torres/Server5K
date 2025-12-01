"""
Módulo: competencia_service
Responsable de la gestión del estado de las competencias.

Características:
- Iniciar/detener competencias
- Notificar cambios de estado a jueces conectados
- Validar transiciones de estado
"""

from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from typing import Dict, Any


class CompetenciaService:
    """
    Servicio para gestionar el ciclo de vida de las competencias.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def iniciar_competencia(self, competencia_id: int) -> Dict[str, Any]:
        """
        Inicia una competencia y notifica a todos los jueces conectados.
        
        Args:
            competencia_id: ID de la competencia a iniciar
            
        Returns:
            Dict con resultado de la operación
        """
        from app.models import Competencia
        
        try:
            competencia = Competencia.objects.get(id=competencia_id)
            
            if competencia.is_running:
                return {
                    'exito': False,
                    'error': 'La competencia ya está en curso'
                }
            
            if not competencia.is_active:
                return {
                    'exito': False,
                    'error': 'La competencia no está activa'
                }
            
            # Verificar si hay otra competencia en curso
            otra_en_curso = Competencia.objects.filter(is_running=True).exclude(id=competencia_id).first()
            if otra_en_curso:
                return {
                    'exito': False,
                    'error': f'No se puede iniciar. La competencia "{otra_en_curso.name}" ya está en curso. Primero debes detenerla.'
                }
            
            # Iniciar competencia
            competencia.is_running = True
            competencia.started_at = timezone.now()
            competencia.save()
            
            # Notificar a todos los jueces de esta competencia
            self._notificar_jueces_competencia(
                competencia_id=competencia.id,
                tipo='competencia_iniciada',
                mensaje='La competencia ha iniciado',
                competencia_nombre=competencia.name,
                en_curso=True,
                started_at=competencia.started_at.isoformat() if competencia.started_at else None
            )
            
            return {
                'exito': True,
                'competencia': competencia
            }
            
        except Competencia.DoesNotExist:
            return {
                'exito': False,
                'error': f'La competencia con ID {competencia_id} no existe'
            }
        except Exception as e:
            return {
                'exito': False,
                'error': f'Error al iniciar competencia: {str(e)}'
            }
    
    def detener_competencia(self, competencia_id: int) -> Dict[str, Any]:
        """
        Detiene una competencia y notifica a todos los jueces conectados.
        
        Args:
            competencia_id: ID de la competencia a detener
            
        Returns:
            Dict con resultado de la operación
        """
        from app.models import Competencia
        
        try:
            competencia = Competencia.objects.get(id=competencia_id)
            
            if not competencia.is_running:
                return {
                    'exito': False,
                    'error': 'La competencia no está en curso'
                }
            
            # Detener competencia
            competencia.is_running = False
            competencia.finished_at = timezone.now()
            competencia.save()
            
            # Notificar a todos los jueces de esta competencia
            self._notificar_jueces_competencia(
                competencia_id=competencia.id,
                tipo='competencia_detenida',
                mensaje='La competencia ha finalizado',
                competencia_nombre=competencia.name,
                en_curso=False,
                started_at=competencia.started_at.isoformat() if competencia.started_at else None,
                finished_at=competencia.finished_at.isoformat() if competencia.finished_at else None
            )
            
            return {
                'exito': True,
                'competencia': competencia
            }
            
        except Competencia.DoesNotExist:
            return {
                'exito': False,
                'error': f'La competencia con ID {competencia_id} no existe'
            }
        except Exception as e:
            return {
                'exito': False,
                'error': f'Error al detener competencia: {str(e)}'
            }
    
    def _notificar_jueces_competencia(
        self,
        competencia_id: int,
        tipo: str,
        mensaje: str,
        competencia_nombre: str,
        en_curso: bool,
        started_at: str = None,
        finished_at: str = None
    ):
        """
        Notifica a todos los jueces de una competencia sobre un cambio de estado.
        
        Args:
            competencia_id: ID de la competencia
            tipo: Tipo de evento ('competencia_iniciada' o 'competencia_detenida')
            mensaje: Mensaje descriptivo
            competencia_nombre: Nombre de la competencia
            en_curso: Estado de la competencia
        """
        if not self.channel_layer:
            return
        
        group_name = f'competencia_{competencia_id}'
        
        async_to_sync(self.channel_layer.group_send)(
            group_name,
            {
                'type': tipo,
                'data': {
                    'mensaje': mensaje,
                    'competencia_id': competencia_id,
                    'competencia_nombre': competencia_nombre,
                    'en_curso': en_curso,
                    'started_at': started_at,
                    'finished_at': finished_at,
                }
            }
        )
    
    def obtener_estado_competencia(self, competencia_id: int) -> Dict[str, Any]:
        """
        Obtiene el estado actual de una competencia.
        
        Args:
            competencia_id: ID de la competencia
            
        Returns:
            Dict con información de la competencia
        """
        from app.models import Competencia
        
        try:
            competencia = Competencia.objects.get(id=competencia_id)
            
            return {
                'exito': True,
                'competencia': {
                    'id': competencia.id,
                    'name': competencia.name,
                    'is_active': competencia.is_active,
                    'is_running': competencia.is_running,
                    'started_at': competencia.started_at.isoformat() if competencia.started_at else None,
                    'finished_at': competencia.finished_at.isoformat() if competencia.finished_at else None,
                    'status': competencia.get_status_display(),
                }
            }
            
        except Competencia.DoesNotExist:
            return {
                'exito': False,
                'error': f'La competencia con ID {competencia_id} no existe'
            }
