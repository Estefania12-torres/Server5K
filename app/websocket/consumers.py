"""
Módulo: consumers
Consumer WebSocket para gestionar las conexiones de jueces y recepción de tiempos en tiempo real.
Responsable de:
- Validar autenticación JWT
- Verificar permisos del juez
- Recibir y procesar registros de tiempo
- Enviar notificaciones en tiempo real
"""

import urllib.parse
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .validators import (
    get_juez_from_token,
    verificar_competencia_activa,
    obtener_estado_competencia,
    validar_datos_registro,
    validar_datos_batch,
)

logger = logging.getLogger(__name__)


class JuezConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer WebSocket para jueces.
    
    Maneja la conexión, autenticación y recepción de tiempos de los jueces.
    Usa Redis como transport layer para mensajería entre workers.
    """
    
    async def connect(self):
        """
        Maneja la conexión inicial del WebSocket.
        
        Valida:
        - Token JWT en query string
        - Que el juez esté activo
        - Que el juez_id de la URL coincida con el token
        - Que la competencia esté activa
        """
        # Expect token in querystring: ?token=...
        qs = self.scope.get('query_string', b'').decode()
        params = urllib.parse.parse_qs(qs)
        token = params.get('token', [None])[0]

        # No loggear tokens ni querystrings (seguridad). Mantener logs mínimos y útiles.
        logger.info("WebSocket connect attempt")
        
        if not token:
            logger.warning("WebSocket rejected: missing token")
            await self.close(code=4001)
            return

        try:
            juez = await get_juez_from_token(token)
            if not juez:
                logger.warning("WebSocket rejected: invalid token or inactive judge")
                await self.close(code=4002)
                return
            logger.info("WebSocket authenticated: juez=%s id=%s", juez.username, juez.id)
        except Exception as e:
            logger.exception("WebSocket token validation error")
            await self.close(code=4000)
            return

        self.juez = juez

        # Verificar que el juez_id de la URL coincida con el juez autenticado
        self.juez_id = str(self.scope['url_route']['kwargs'].get('juez_id'))
        logger.debug("Verifying juez_id: url=%s token=%s", self.juez_id, self.juez.id)
        
        if str(self.juez.id) != self.juez_id:
            logger.warning("WebSocket rejected: juez_id mismatch url=%s token=%s", self.juez_id, self.juez.id)
            await self.close(code=4003)
            return

        # Verificar que la competencia esté activa
        logger.debug("Checking active competition for juez_id=%s", self.juez_id)
        competencia_activa = await verificar_competencia_activa(self.juez)
        if not competencia_activa:
            logger.warning("WebSocket rejected: no active competition juez_id=%s", self.juez_id)
            await self.close(code=4004)
            return

        logger.debug("Active competition verified juez_id=%s", self.juez_id)
        
        # Unirse al grupo del juez y al grupo de la competencia
        self.group_name = f'juez_{self.juez_id}'
        
        # Obtener competencia_id del equipo asignado al juez (async)
        competencia_id = await self.get_competencia_id_del_juez()
        
        if competencia_id:
            self.competencia_group = f'competencia_{competencia_id}'
            await self.channel_layer.group_add(self.competencia_group, self.channel_name)
            logger.debug("Joined group %s for juez_id=%s", self.competencia_group, self.juez_id)
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        
        logger.info("WebSocket accepted: juez_id=%s", self.juez_id)
        await self.accept()
        
        # Enviar estado de la competencia al conectar
        estado_competencia = await obtener_estado_competencia(self.juez)
        logger.debug("Sending initial competition state juez_id=%s state=%s", self.juez_id, estado_competencia)
        await self.send_json({
            'tipo': 'conexion_establecida',
            'mensaje': 'Conectado exitosamente',
            'competencia': estado_competencia
        })
        logger.info("WebSocket ready: juez=%s id=%s", self.juez.username, self.juez_id)

    @database_sync_to_async
    def get_competencia_id_del_juez(self):
        """
        Obtiene el ID de la competencia del primer equipo del juez.
        Debe ser async porque accede a la base de datos.
        """
        equipo = self.juez.teams.select_related('competition').first()
        if equipo:
            logger.debug("Team found: equipo=%s competencia=%s", equipo.name, equipo.competition.name)
            return equipo.competition_id
        logger.warning("Judge has no assigned teams juez_id=%s", self.juez_id)
        return None

    async def disconnect(self, close_code):
        """
        Maneja la desconexión del WebSocket.
        Remueve al juez de los grupos de Redis.
        """
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_discard(self.competencia_group, self.channel_name)
        except Exception:
            pass
        logger.info("WebSocket disconnected: juez_id=%s code=%s", getattr(self, 'juez_id', None), close_code)

    async def receive_json(self, content, **kwargs):
        """
        Maneja mensajes JSON del cliente.
        
        Mensajes soportados:
        1. ping: Mantiene la conexión viva (heartbeat)
        
        NOTA: Los registros de tiempo ahora se envían por HTTP POST
        a /api/equipos/{id}/registros/ para mayor confiabilidad.
        El WebSocket solo se usa para notificaciones en tiempo real.
        """
        tipo = content.get('tipo')
        
        if tipo == 'ping':
            # Responder al heartbeat
            await self.send_json({
                'tipo': 'pong',
                'mensaje': 'Conexión activa'
            })
        elif tipo == 'registrar_tiempo' or tipo == 'registrar_tiempos':
            # Informar al cliente que debe usar HTTP
            await self.send_json({
                'tipo': 'error',
                'mensaje': 'Los registros ahora se envían por HTTP POST a /api/equipos/{id}/registros/',
                'usar_http': True
            })
        else:
            # Mensaje no reconocido
            await self.send_json({
                'tipo': 'error',
                'mensaje': f'Tipo de mensaje no reconocido: {tipo}'
            })
    
    async def manejar_registro_tiempo(self, content):
        """
        Registra el tiempo de un equipo.
        
        Esperado en content:
        {
            "tipo": "registrar_tiempo",
            "equipo_id": 1,
            "tiempo": 1234567,  # milisegundos totales
            "horas": 0,
            "minutos": 20,
            "segundos": 34,
            "milisegundos": 567
        }
        """
        try:
            # Validar datos básicos
            es_valido, error = validar_datos_registro(content)
            if not es_valido:
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': error
                })
                return
            
            equipo_id = content.get('equipo_id')
            tiempo = content.get('tiempo')
            horas = content.get('horas', 0)
            minutos = content.get('minutos', 0)
            segundos = content.get('segundos', 0)
            milisegundos = content.get('milisegundos', 0)
            
            # Registrar el tiempo usando el servicio
            from app.services.registro_service import RegistroService
            
            service = RegistroService()
            resultado = await service.registrar_tiempo(
                juez=self.juez,
                equipo_id=equipo_id,
                tiempo=tiempo,
                horas=horas,
                minutos=minutos,
                segundos=segundos,
                milisegundos=milisegundos
            )
            
            if resultado['exito']:
                registro = resultado['registro']
                # Enviar confirmación al cliente
                await self.send_json({
                    'tipo': 'tiempo_registrado',
                    'registro': {
                        'id_registro': str(registro.record_id),
                        'equipo_id': registro.team_id,
                        'equipo_nombre': registro.team.name,
                        'equipo_dorsal': registro.team.number,
                        'tiempo': registro.time,
                        'horas': registro.hours,
                        'minutos': registro.minutes,
                        'segundos': registro.seconds,
                        'milisegundos': registro.milliseconds,
                        'timestamp': registro.created_at.isoformat()
                    }
                })
            else:
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': resultado['error']
                })
            
        except Exception as e:
            await self.send_json({
                'tipo': 'error',
                'mensaje': f'Error al registrar tiempo: {str(e)}'
            })
    
    async def manejar_registro_tiempos_batch(self, content):
        """
        Registra múltiples tiempos en batch (lote).
        
        Esperado en content:
        {
            "tipo": "registrar_tiempos",
            "equipo_id": 1,
            "registros": [
                {
                    "tiempo": 1234567,
                    "horas": 0,
                    "minutos": 20,
                    "segundos": 34,
                    "milisegundos": 567
                },
                ...
            ]
        }
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Log de debug: recibimos el mensaje
            logger.debug("[BATCH] Batch recibido: juez=%s equipo_id=%s", self.juez.username, content.get('equipo_id'))
            logger.debug("[BATCH] Total registros recibidos: %s", len(content.get('registros', [])))
            
            # Validar datos del batch
            es_valido, error = validar_datos_batch(content)
            if not es_valido:
                logger.warning(f"[BATCH] Validación fallida: {error}")
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': error
                })
                return
            
            equipo_id = content.get('equipo_id')
            registros = content.get('registros', [])
            
            # Procesar batch usando el servicio
            from app.services.registro_service import RegistroService
            
            service = RegistroService()
            resultado = await service.registrar_batch(
                juez=self.juez,
                equipo_id=equipo_id,
                registros=registros
            )
            
            # Log de resultado
            logger.info(
                "[BATCH] Resultado: guardados=%s fallidos=%s juez=%s equipo_id=%s",
                resultado['total_guardados'],
                resultado['total_fallidos'],
                self.juez.username,
                equipo_id,
            )
            
            if resultado['total_fallidos'] > 0:
                logger.warning(f"[BATCH] Detalles de fallos: {resultado['registros_fallidos']}")

            # Enviar respuesta con resumen
            await self.send_json({
                'tipo': 'tiempos_registrados_batch',
                'total_enviados': resultado['total_enviados'],
                'total_guardados': resultado['total_guardados'],
                'total_fallidos': resultado['total_fallidos'],
                'registros_guardados': resultado['registros_guardados'],
                'registros_fallidos': resultado['registros_fallidos']
            })
            
            logger.debug("[BATCH] Respuesta enviada al cliente")
            
        except Exception as e:
            logger.error(f"[BATCH] Error crítico: {str(e)}", exc_info=True)
            await self.send_json({
                'tipo': 'error',
                'mensaje': f'Error al procesar batch: {str(e)}'
            })

    # Manejadores de eventos de grupo
    async def competencia_iniciada(self, event):
        """
        Notifica al cliente que la competencia ha iniciado.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Evento frecuente: mantener en DEBUG para evitar ruido.
        logger.debug("Event competencia_iniciada received juez_id=%s", self.juez_id)
        
        data = event.get('data', {})
        
        mensaje_a_enviar = {
            'tipo': 'competencia_iniciada',
            'mensaje': data.get('mensaje', 'La competencia ha iniciado'),
            'competencia': {
                'id': data.get('competencia_id'),
                'nombre': data.get('competencia_nombre'),
                'en_curso': data.get('en_curso', True),
                'started_at': data.get('started_at'),  # Timestamp de inicio del servidor
            }
        }
        
        logger.debug("Sending competencia_iniciada to client juez_id=%s", self.juez_id)
        
        await self.send_json(mensaje_a_enviar)
        logger.debug("competencia_iniciada sent juez_id=%s", self.juez_id)
        
    
    async def competencia_detenida(self, event):
        """
        Notifica al cliente que la competencia ha finalizado.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug("Event competencia_detenida received juez_id=%s", self.juez_id)
        
        data = event.get('data', {})
        
        mensaje_a_enviar = {
            'tipo': 'competencia_detenida',
            'mensaje': data.get('mensaje', 'La competencia ha finalizado'),
            'competencia': {
                'id': data.get('competencia_id'),
                'nombre': data.get('competencia_nombre'),
                'started_at': data.get('started_at'),  # Timestamp de inicio
                'finished_at': data.get('finished_at'),  # Timestamp de finalización
                'en_curso': data.get('en_curso', False),
            }
        }
        
        logger.debug("Sending competencia_detenida to client juez_id=%s", self.juez_id)
        
        await self.send_json(mensaje_a_enviar)
        
        logger.debug("competencia_detenida sent juez_id=%s", self.juez_id)

    async def registros_actualizados(self, event):
        """
        Notifica al cliente que hay nuevos registros de tiempo.
        Este evento se dispara cuando se guardan registros por HTTP.
        Permite actualizar la UI en tiempo real.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug("Event registros_actualizados received juez_id=%s", self.juez_id)
        
        data = event.get('data', {})
        
        mensaje_a_enviar = {
            'tipo': 'registros_actualizados',
            'equipo': {
                'id': data.get('equipo_id'),
                'nombre': data.get('equipo_nombre'),
                'dorsal': data.get('equipo_dorsal'),
            },
            'total_registros': data.get('total_registros'),
            'tiempo_total': data.get('tiempo_total'),
        }
        
        await self.send_json(mensaje_a_enviar)

        logger.debug("registros_actualizados sent juez_id=%s", self.juez_id)


class CompetenciaPublicConsumer(AsyncJsonWebsocketConsumer):
    """Consumer WebSocket público para ver resultados en vivo.

    Se suscribe al grupo `competencia_<id>` y reenvía eventos al navegador.
    """

    async def connect(self):
        competencia_id = str(self.scope['url_route']['kwargs'].get('competencia_id'))
        if not competencia_id:
            await self.close(code=4400)
            return

        self.competencia_id = competencia_id
        self.group_name = f'competencia_{self.competencia_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_json({
            'tipo': 'conexion_establecida',
            'competencia_id': int(self.competencia_id),
        })

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
        if content.get('tipo') == 'ping':
            await self.send_json({'tipo': 'pong'})

    async def registros_actualizados(self, event):
        data = event.get('data', {})
        await self.send_json({
            'tipo': 'registros_actualizados',
            'data': data,
        })

    async def competencia_iniciada(self, event):
        await self.send_json({
            'tipo': 'competencia_iniciada',
            'data': event.get('data', {}),
        })

    async def competencia_detenida(self, event):
        await self.send_json({
            'tipo': 'competencia_detenida',
            'data': event.get('data', {}),
        })