"""
Módulo: signals
Señales de Django para notificar cambios en tiempo real vía WebSocket.
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from app.models import Competencia

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Competencia)
def competencia_pre_save(sender, instance, **kwargs):
    """
    Guarda el estado anterior de is_running antes de guardar.
    """
    if instance.pk:
        try:
            instance._previous_is_running = Competencia.objects.get(pk=instance.pk).is_running
        except Competencia.DoesNotExist:
            instance._previous_is_running = False
    else:
        instance._previous_is_running = False


@receiver(post_save, sender=Competencia)
def competencia_estado_cambiado(sender, instance, created, **kwargs):
    """
    Notifica a los jueces cuando cambia el estado de una competencia.
    Se dispara cuando se cambia is_running desde el admin de Django.
    """
    # Solo notificar si no es una creación y el estado cambió
    if created:
        return
    
    previous_is_running = getattr(instance, '_previous_is_running', False)
    
    # Si el estado no cambió, no hacer nada
    if previous_is_running == instance.is_running:
        return
    
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("Channel layer no disponible; no se puede enviar notificación")
        return
    
    group_name = f'competencia_{instance.id}'
    
    # Determinar el tipo de evento
    if instance.is_running:
        tipo_evento = 'competencia_iniciada'
        mensaje = 'La competencia ha iniciado'
        logger.info("Competencia iniciada: %s (id=%s)", instance.name, instance.id)
    else:
        tipo_evento = 'competencia_detenida'
        mensaje = 'La competencia ha finalizado'
        logger.info("Competencia detenida: %s (id=%s)", instance.name, instance.id)
    
    # Enviar notificación al grupo de la competencia
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': tipo_evento,
                'data': {
                    'mensaje': mensaje,
                    'competencia_id': instance.id,
                    'competencia_nombre': instance.name,
                    'en_curso': instance.is_running,
                }
            }
        )
        logger.debug("Notificación enviada al grupo %s: %s", group_name, tipo_evento)
    except Exception as e:
        logger.error("Error enviando notificación WebSocket: %s", e, exc_info=True)
