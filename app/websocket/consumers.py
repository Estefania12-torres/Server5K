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
        
        logger.info(f"Intento de conexión WebSocket")
        logger.info(f" Query string: {qs[:100]}...")
        logger.info(f" Token extraído: {token[:50] if token else 'None'}...")
        
        if not token:
            logger.error(" Token no proporcionado - Rechazando conexión")
            await self.close(code=4001)
            return

        try:
            juez = await get_juez_from_token(token)
            if not juez:
                logger.error(" Token inválido o juez no encontrado - Rechazando conexión")
                await self.close(code=4002)
                return
            logger.info(f" Token válido - Juez: {juez.username} (ID: {juez.id})")
        except Exception as e:
            logger.error(f" Error validando token: {e}")
            await self.close(code=4000)
            return

        self.juez = juez

        # Verificar que el juez_id de la URL coincida con el juez autenticado
        self.juez_id = str(self.scope['url_route']['kwargs'].get('juez_id'))
        logger.info(f" Verificando juez_id - URL: {self.juez_id}, Token: {self.juez.id}")
        
        if str(self.juez.id) != self.juez_id:
            logger.error(f" Juez ID no coincide - URL: {self.juez_id}, Token: {self.juez.id}")
            await self.close(code=4003)
            return
        
        logger.info(" Juez ID coincide")
        # Verificar que la competencia esté activa
        logger.info(" Verificando competencia activa...")
        competencia_activa = await verificar_competencia_activa(self.juez)
        if not competencia_activa:
            logger.error(f" Juez {self.juez_id} no tiene competencia activa")
            await self.close(code=4004)
            return
        
        logger.info("✅ Competencia activa verificada")
        
        # Unirse al grupo del juez y al grupo de la competencia
        self.group_name = f'juez_{self.juez_id}'
        
        # Obtener competencia_id del equipo asignado al juez (async)
        competencia_id = await self.get_competencia_id_del_juez()
        
        if competencia_id:
            self.competencia_group = f'competencia_{competencia_id}'
            await self.channel_layer.group_add(self.competencia_group, self.channel_name)
            logger.info(f"📢 Juez {self.juez_id} unido al grupo {self.competencia_group}")
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        
        logger.info(f" Aceptando conexión WebSocket para juez {self.juez_id}")
        await self.accept()
        
        # Enviar estado de la competencia al conectar
        estado_competencia = await obtener_estado_competencia(self.juez)
        logger.info(f" Enviando estado inicial - Competencia: {estado_competencia}")
        await self.send_json({
            'tipo': 'conexion_establecida',
            'mensaje': 'Conectado exitosamente',
            'competencia': estado_competencia
        })
        
        logger.info(f"✅✅✅ Conexión WebSocket establecida exitosamente para juez {self.juez.username} (ID: {self.juez_id})")

    @database_sync_to_async
    def get_competencia_id_del_juez(self):
        """
        Obtiene el ID de la competencia del primer equipo del juez.
        Debe ser async porque accede a la base de datos.
        """
        equipo = self.juez.teams.select_related('competition').first()
        if equipo:
            logger.debug(f"🔍 Equipo encontrado: {equipo.name} - Competencia: {equipo.competition.name}")
            return equipo.competition_id
        logger.warning(f"⚠️ Juez {self.juez_id} no tiene equipos asignados")
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
            logger.info(f"[BATCH] Juez {self.juez.username} - Recibido batch para equipo {content.get('equipo_id')}")
            logger.info(f"[BATCH] Total registros en batch: {len(content.get('registros', []))}")
            
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
            logger.info(f"[BATCH] Resultado - Guardados: {resultado['total_guardados']}, Fallidos: {resultado['total_fallidos']}")
            
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
            
            logger.info(f"[BATCH] Respuesta enviada al cliente")
            
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
        
        logger.info(f"🔔 MÉTODO competencia_iniciada EJECUTADO para juez {self.juez_id}")
        logger.info(f"   Event recibido: {event}")
        
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
        
        logger.info(f"   📤 Enviando al cliente: {mensaje_a_enviar}")
        
        await self.send_json(mensaje_a_enviar)
        
        logger.info(f"   ✅ Mensaje enviado exitosamente al juez {self.juez_id}")
        
    
    async def competencia_detenida(self, event):
        """
        Notifica al cliente que la competencia ha finalizado.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"  MÉTODO competencia_detenida EJECUTADO para juez {self.juez_id}")
        logger.info(f"  Event recibido: {event}")
        
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
        
        logger.info(f"  Enviando al cliente: {mensaje_a_enviar}")
        
        await self.send_json(mensaje_a_enviar)
        
        logger.info(f"  Mensaje enviado exitosamente al juez {self.juez_id}")

    async def registros_actualizados(self, event):
        """
        Notifica al cliente que hay nuevos registros de tiempo.
        Este evento se dispara cuando se guardan registros por HTTP.
        Permite actualizar la UI en tiempo real.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"MÉTODO registros_actualizados EJECUTADO para juez {self.juez_id}")
        
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
        
        logger.info(f"   Notificación de registros enviada al juez {self.juez_id}")