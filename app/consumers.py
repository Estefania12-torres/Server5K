import urllib.parse
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async


@database_sync_to_async
def get_juez_from_token(token):
    """
    Valida el token JWT y retorna el juez.
    """
    from rest_framework_simplejwt.tokens import AccessToken
    from .models import Juez
    
    try:
        # Validar el token
        access_token = AccessToken(token)
        juez_id = access_token.get('juez_id')
        
        if not juez_id:
            return None
        
        # Obtener el juez con su competencia (select_related para optimizar)
        juez = Juez.objects.select_related('competencia').get(id=juez_id, activo=True)
        return juez
    except Exception:
        return None


@database_sync_to_async
def verificar_competencia_activa(juez):
    """
    Verifica que el juez tenga una competencia activa.
    """
    return juez.competencia and juez.competencia.activa


@database_sync_to_async
def obtener_estado_competencia(juez):
    """
    Obtiene el estado de la competencia del juez.
    """
    if not juez.competencia:
        return None
    
    return {
        'id': juez.competencia.id,
        'nombre': juez.competencia.nombre,
        'en_curso': juez.competencia.en_curso,
        'activa': juez.competencia.activa,
    }


class JuezConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Expect token in querystring: ?token=...
        qs = self.scope.get('query_string', b'').decode()
        params = urllib.parse.parse_qs(qs)
        token = params.get('token', [None])[0]
        if not token:
            await self.close()
            return

        try:
            juez = await get_juez_from_token(token)
            if not juez:
                await self.close()
                return
        except Exception:
            await self.close()
            return

        self.juez = juez

        # Verificar que el juez_id de la URL coincida con el juez autenticado
        self.juez_id = str(self.scope['url_route']['kwargs'].get('juez_id'))
        if str(self.juez.id) != self.juez_id:
            await self.close()
            return

        # Verificar que la competencia esté activa (puede conectarse pero no enviar tiempos hasta que inicie)
        competencia_activa = await verificar_competencia_activa(self.juez)
        if not competencia_activa:
            await self.close()
            return

        self.group_name = f'juez_{self.juez_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Enviar estado de la competencia al conectar
        estado_competencia = await obtener_estado_competencia(self.juez)
        await self.send_json({
            'tipo': 'conexion_establecida',
            'mensaje': 'Conectado exitosamente',
            'competencia': estado_competencia
        })

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
        """
        Maneja mensajes JSON del cliente.
        
        Mensajes soportados:
        1. registrar_tiempo: Registra el tiempo de llegada de un equipo
        2. registrar_tiempos: Registra múltiples tiempos en batch
        """
        tipo = content.get('tipo')
        
        if tipo == 'registrar_tiempo':
            await self.manejar_registro_tiempo(content)
        elif tipo == 'registrar_tiempos':
            await self.manejar_registro_tiempos_batch(content)
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
            equipo_id = content.get('equipo_id')
            tiempo = content.get('tiempo')
            horas = content.get('horas', 0)
            minutos = content.get('minutos', 0)
            segundos = content.get('segundos', 0)
            milisegundos = content.get('milisegundos', 0)
            
            # Validar que se enviaron todos los datos
            if equipo_id is None or tiempo is None:
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': 'Faltan datos requeridos: equipo_id y tiempo son obligatorios'
                })
                return
            
            # Registrar el tiempo en la base de datos
            registro = await self.guardar_registro_tiempo(
                equipo_id=equipo_id,
                tiempo=tiempo,
                horas=horas,
                minutos=minutos,
                segundos=segundos,
                milisegundos=milisegundos
            )
            
            if registro:
                # Enviar confirmación al cliente
                await self.send_json({
                    'tipo': 'tiempo_registrado',
                    'registro': {
                        'id_registro': str(registro.id_registro),
                        'equipo_id': registro.equipo_id,
                        'equipo_nombre': registro.equipo.nombre,
                        'equipo_dorsal': registro.equipo.dorsal,
                        'tiempo': registro.tiempo,
                        'horas': registro.horas,
                        'minutos': registro.minutos,
                        'segundos': registro.segundos,
                        'milisegundos': registro.milisegundos,
                        'timestamp': registro.timestamp.isoformat()
                    }
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
        try:
            equipo_id = content.get('equipo_id')
            registros = content.get('registros', [])
            
            # Validar datos
            if equipo_id is None:
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': 'Falta el equipo_id'
                })
                return
            
            if not registros or not isinstance(registros, list):
                await self.send_json({
                    'tipo': 'error',
                    'mensaje': 'Faltan los registros o no es una lista válida'
                })
                return
            
            # Procesar cada registro
            registros_guardados = []
            registros_fallidos = []
            
            for idx, reg in enumerate(registros):
                try:
                    tiempo = reg.get('tiempo')
                    horas = reg.get('horas', 0)
                    minutos = reg.get('minutos', 0)
                    segundos = reg.get('segundos', 0)
                    milisegundos = reg.get('milisegundos', 0)
                    
                    if tiempo is None:
                        registros_fallidos.append({
                            'indice': idx,
                            'error': 'Falta el campo tiempo'
                        })
                        continue
                    
                    # Guardar el registro
                    registro = await self.guardar_registro_tiempo(
                        equipo_id=equipo_id,
                        tiempo=tiempo,
                        horas=horas,
                        minutos=minutos,
                        segundos=segundos,
                        milisegundos=milisegundos
                    )
                    
                    if registro:
                        registros_guardados.append({
                            'indice': idx,
                            'id_registro': str(registro.id_registro),
                            'tiempo': registro.tiempo
                        })
                    
                except Exception as e:
                    registros_fallidos.append({
                        'indice': idx,
                        'error': str(e)
                    })
            
            # Enviar respuesta con resumen
            await self.send_json({
                'tipo': 'tiempos_registrados_batch',
                'total_enviados': len(registros),
                'total_guardados': len(registros_guardados),
                'total_fallidos': len(registros_fallidos),
                'registros_guardados': registros_guardados,
                'registros_fallidos': registros_fallidos
            })
            
        except Exception as e:
            await self.send_json({
                'tipo': 'error',
                'mensaje': f'Error al procesar batch: {str(e)}'
            })
    
    @database_sync_to_async
    def guardar_registro_tiempo(self, equipo_id, tiempo, horas, minutos, segundos, milisegundos):
        """
        Guarda el registro de tiempo en la base de datos.
        Valida que el equipo pertenezca al juez autenticado.
        Valida que la competencia esté en curso.
        """
        from .models import Equipo, RegistroTiempo
        
        try:
            # Refrescar el juez con su competencia para tener datos actualizados
            from .models import Juez
            juez_actualizado = Juez.objects.select_related('competencia').get(id=self.juez.id)
            
            # Verificar que la competencia esté en curso
            if not juez_actualizado.competencia or not juez_actualizado.competencia.en_curso:
                raise ValueError(
                    'No se pueden registrar tiempos. La competencia no ha iniciado o ya finalizó.'
                )
            
            # Verificar que el equipo existe
            equipo = Equipo.objects.get(id=equipo_id)
            
            # Verificar que el equipo pertenece a este juez
            if equipo.juez_asignado_id != self.juez.id:
                raise ValueError(
                    f'El equipo con ID {equipo_id} no pertenece a tu lista de equipos asignados'
                )
            
            # Crear el registro de tiempo
            registro = RegistroTiempo.objects.create(
                equipo=equipo,
                tiempo=tiempo,
                horas=horas,
                minutos=minutos,
                segundos=segundos,
                milisegundos=milisegundos
            )
            
            return registro
            
        except Equipo.DoesNotExist:
            raise ValueError(f'El equipo con ID {equipo_id} no existe')
        except Exception as e:
            raise Exception(f'Error al guardar registro: {str(e)}')

    async def competencia_iniciada(self, event):
        """
        Notifica al cliente que la competencia ha iniciado.
        Ahora puede enviar registros de tiempos.
        """
        await self.send_json({
            'tipo': 'competencia_iniciada',
            'mensaje': event['data']['mensaje'],
            'competencia': {
                'id': event['data']['competencia_id'],
                'nombre': event['data']['competencia_nombre'],
                'en_curso': event['data']['en_curso'],
            }
        })
    
    async def competencia_detenida(self, event):
        """
        Notifica al cliente que la competencia ha finalizado.
        Ya no puede enviar más registros de tiempos.
        """
        await self.send_json({
            'tipo': 'competencia_detenida',
            'mensaje': event['data']['mensaje'],
            'competencia': {
                'id': event['data']['competencia_id'],
                'nombre': event['data']['competencia_nombre'],
                'en_curso': event['data']['en_curso'],
            }
        })

    async def carrera_iniciada(self, event):
        """Mantener compatibilidad con código antiguo"""
        await self.send_json({
            'type': 'carrera.iniciada',
            'data': event.get('data', {})
        })
