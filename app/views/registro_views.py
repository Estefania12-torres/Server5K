"""
Módulo: registro_views
Vistas API REST para el registro de tiempos.
Implementa endpoints HTTP para enviar registros (más confiable que WebSocket).
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import uuid
import logging

from app.models import Equipo, RegistroTiempo, Juez

logger = logging.getLogger(__name__)


class RegistrarTiemposView(APIView):
    """
    POST /api/equipos/{equipo_id}/registros/
    
    Registra los 15 tiempos de un equipo de manera atómica.
    Solo el juez asignado al equipo puede enviar registros.
    
    Request Body:
    {
        "registros": [
            {
                "id_registro": "uuid-opcional",
                "tiempo": 125000,
                "horas": 0,
                "minutos": 2,
                "segundos": 5,
                "milisegundos": 0
            },
            ...
        ]
    }
    
    Response (201 Created):
    {
        "exito": true,
        "mensaje": "Registros guardados exitosamente",
        "equipo_id": 1,
        "equipo_nombre": "Los Veloces",
        "total_guardados": 15,
        "registros": [...]
    }
    """
    
    permission_classes = [IsAuthenticated]
    MAX_REGISTROS = 15
    
    def post(self, request, equipo_id):
        juez = request.user
        
        logger.info(f"[HTTP] Juez {juez.username} enviando registros para equipo {equipo_id}")
        
        # Validar que el usuario sea un Juez
        if not isinstance(juez, Juez):
            try:
                juez = Juez.objects.get(id=juez.id)
            except Juez.DoesNotExist:
                return Response(
                    {"exito": False, "error": "Usuario no es un juez válido"},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Obtener registros del body
        registros = request.data.get('registros', [])
        
        if not registros:
            return Response(
                {"exito": False, "error": "No se enviaron registros"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # VALIDACIÓN ESTRICTA: Deben ser exactamente 15 registros
        if len(registros) != self.MAX_REGISTROS:
            return Response(
                {"exito": False, "error": f"Se requieren exactamente {self.MAX_REGISTROS} registros. Recibidos: {len(registros)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Verificar que el juez tenga equipos asignados
                equipos_juez = juez.teams.select_related('competition').all()
                if not equipos_juez.exists():
                    return Response(
                        {"exito": False, "error": "No tienes equipos asignados"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Verificar que la competencia esté en curso
                competencia = equipos_juez.first().competition
                if not competencia or not competencia.is_running:
                    return Response(
                        {"exito": False, "error": "La competencia no está en curso"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Obtener el equipo y verificar pertenencia
                try:
                    equipo = Equipo.objects.select_for_update().get(id=equipo_id)
                except Equipo.DoesNotExist:
                    return Response(
                        {"exito": False, "error": f"Equipo {equipo_id} no existe"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                if equipo.judge_id != juez.id:
                    return Response(
                        {"exito": False, "error": "Este equipo no te pertenece"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Delegar creación en el servicio (usa bulk_create + idempotencia)
                from app.services.registro_service import RegistroService
                servicio = RegistroService()
                # Usar versión SÍNCRONA para evitar problemas de conexión en vistas HTTP
                resultado = servicio.registrar_batch_sync(juez=juez, equipo_id=equipo.id, registros=registros)

                logger.info(f"[HTTP] ✅ Guardados: {resultado['total_guardados']} | Fallidos: {resultado['total_fallidos']} para equipo {equipo.name}")

                if resultado['total_guardados'] == 0 and resultado['total_fallidos'] > 0:
                    return Response({"exito": False, "error": resultado['registros_fallidos']}, status=status.HTTP_400_BAD_REQUEST)

                # Notificar por WebSocket a la UI pública
                self._notificar_actualizacion(equipo, resultado['registros_guardados'])
                
                return Response({
                    "exito": True,
                    "mensaje": "Registros guardados exitosamente",
                    "equipo_id": equipo.id,
                    "equipo_nombre": equipo.name,
                    "equipo_dorsal": equipo.number,
                    "total_guardados": resultado['total_guardados'],
                    "registros": resultado['registros_guardados'],
                    "registros_fallidos": resultado['registros_fallidos'],
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"[HTTP] Error guardando registros: {str(e)}")
            return Response(
                {"exito": False, "error": f"Error interno: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _notificar_actualizacion(self, equipo, registros):
        """
        Notifica a los clientes conectados que hay nuevos registros.
        Esto permite actualizar la UI pública en tiempo real.
        """
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                competencia_group = f'competencia_{equipo.competition_id}'
                
                # Calcular tiempo total
                tiempo_total = sum(r['tiempo'] for r in registros if not r.get('duplicado', False))
                
                async_to_sync(channel_layer.group_send)(
                    competencia_group,
                    {
                        'type': 'registros_actualizados',
                        'data': {
                            'equipo_id': equipo.id,
                            'equipo_nombre': equipo.name,
                            'equipo_dorsal': equipo.number,
                            'total_registros': len(registros),
                            'tiempo_total': tiempo_total,
                        }
                    }
                )
                logger.info(f"[WS] Notificación enviada al grupo {competencia_group}")
        except Exception as e:
            logger.warning(f"[WS] No se pudo notificar por WebSocket: {e}")


class EstadoEquipoRegistrosView(APIView):
    """
    GET /api/equipos/{equipo_id}/registros/estado/
    
    Verifica el estado de registros de un equipo.
    Útil para saber si ya se enviaron los tiempos.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, equipo_id):
        juez = request.user
        
        try:
            equipo = Equipo.objects.get(id=equipo_id)
        except Equipo.DoesNotExist:
            return Response(
                {"error": "Equipo no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Contar registros
        total_registros = RegistroTiempo.objects.filter(team=equipo).count()
        
        # Obtener registros ordenados
        registros = RegistroTiempo.objects.filter(team=equipo).order_by('time')
        
        registros_data = [{
            'id_registro': str(r.record_id),
            'tiempo': r.time,
            'horas': r.hours,
            'minutos': r.minutes,
            'segundos': r.seconds,
            'milisegundos': r.milliseconds,
        } for r in registros]
        
        return Response({
            "equipo_id": equipo.id,
            "equipo_nombre": equipo.name,
            "total_registros": total_registros,
            "maximo_registros": 15,
            "puede_enviar": total_registros == 0,
            "registros": registros_data
        })
