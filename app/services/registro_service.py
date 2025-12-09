from django.db import transaction
from channels.db import database_sync_to_async
from typing import Dict, List, Any
import uuid


class RegistroService:
    
    MAX_REGISTROS_POR_EQUIPO = 15
    
    @database_sync_to_async
    def registrar_tiempo(
        self,
        juez,
        equipo_id: int,
        time: int,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        milliseconds: int = 0,
        record_id: str = None
    ) -> Dict[str, Any]:
        """
        Registra un tiempo para un equipo de manera segura y atómica.
        
        Args:
            juez: Instancia del modelo Juez
            equipo_id: ID del equipo
            time: Tiempo total en milisegundos
            hours: Componente de horas
            minutes: Componente de minutos
            seconds: Componente de segundos
            milliseconds: Componente de milisegundos
            record_id: UUID opcional para idempotencia
            
        Returns:
            Dict con claves 'exito', 'registro' (si exitoso) o 'error' (si falla)
        """
        from app.models import Equipo, RegistroTiempo, Juez
        
        try:
            with transaction.atomic():
                # Refrescar el juez con su equipo asignado
                juez_actualizado = Juez.objects.prefetch_related('teams', 'teams__competition').get(id=juez.id)
                
                # Verificar que el juez tenga equipos asignados
                equipos = juez_actualizado.teams.all()
                if not equipos:
                    return {
                        'exito': False,
                        'error': 'El juez no tiene equipos asignados'
                    }

                # Obtener la competencia del primer equipo
                competencia_juez = equipos.first().competition
                
                # Verificar que la competencia esté en curso
                if not competencia_juez or not competencia_juez.is_running:
                    return {
                        'exito': False,
                        'error': 'No se pueden registrar tiempos. La competencia no ha iniciado o ya finalizó.'
                    }
                
                # Verificar que el equipo existe y pertenece a este juez
                try:
                    equipo = Equipo.objects.select_for_update().get(id=equipo_id)
                except Equipo.DoesNotExist:
                    return {
                        'exito': False,
                        'error': f'El equipo con ID {equipo_id} no existe'
                    }
                
                if equipo.judge_id != juez.id:
                    return {
                        'exito': False,
                        'error': f'El equipo con ID {equipo_id} no pertenece a tu lista de equipos asignados'
                    }
                
                # Verificar si ya existe un registro con este record_id (idempotencia)
                if record_id:
                    registro_existente = RegistroTiempo.objects.filter(
                        record_id=record_id
                    ).first()
                    
                    if registro_existente:
                        return {
                            'exito': True,
                            'registro': registro_existente,
                            'duplicado': True
                        }
                
                # Contar registros actuales del equipo en esta competencia
                num_registros = RegistroTiempo.objects.filter(team=equipo).count()
                
                if num_registros >= self.MAX_REGISTROS_POR_EQUIPO:
                    return {
                        'exito': False,
                        'error': f'El equipo ya completó sus {self.MAX_REGISTROS_POR_EQUIPO} registros. No se permiten registros adicionales.'
                    }
                
                # Construir registro y usar bulk_create con ignore_conflicts para idempotencia
                registro = RegistroTiempo(
                    record_id=record_id or uuid.uuid4(),
                    team=equipo,
                    time=time,
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                    milliseconds=milliseconds
                )
                
                creados = RegistroTiempo.objects.bulk_create(
                    [registro],
                    ignore_conflicts=True  # si llega un UUID repetido no rompe la transacción
                )
                
                if not creados:
                    # Ya existía; devolver como duplicado
                    existente = RegistroTiempo.objects.get(record_id=registro.record_id)
                    return {
                        'exito': True,
                        'registro': existente,
                        'duplicado': True
                    }
                
                return {
                    'exito': True,
                    'registro': creados[0],
                    'duplicado': False
                }
                
        except Exception as e:
            return {
                'exito': False,
                'error': f'Error al guardar registro: {str(e)}'
            }
    
    def registrar_batch_sync(
        self,
        juez,
        equipo_id: int,
        registros: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Versión SÍNCRONA de registrar_batch para uso desde vistas HTTP.
        Evita problemas de conexión cuando se llama desde async_to_sync.
        """
        return self._registrar_batch_impl(juez, equipo_id, registros)
    
    @database_sync_to_async
    def registrar_batch(
        self,
        juez,
        equipo_id: int,
        registros: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Versión ASÍNCRONA de registrar_batch para uso desde WebSocket.
        """
        return self._registrar_batch_impl(juez, equipo_id, registros)
    
    def _registrar_batch_impl(
        self,
        juez,
        equipo_id: int,
        registros: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Registra múltiples tiempos en batch de manera transaccional.
        
        Args:
            juez: Instancia del modelo Juez
            equipo_id: ID del equipo
            registros: Lista de diccionarios con datos de registros
            
        Returns:
            Dict con resumen de registros guardados y fallidos
        """
        from app.models import Equipo, RegistroTiempo, Juez
        
        registros_guardados = []
        registros_fallidos = []
        
        try:
            with transaction.atomic():
                # Refrescar el juez con sus equipos asignados
                juez_actualizado = Juez.objects.prefetch_related('teams', 'teams__competition').get(id=juez.id)
                
                # Verificar que el juez tenga equipos asignados
                equipos = juez_actualizado.teams.all()
                if not equipos:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros),
                        'registros_guardados': [],
                        'registros_fallidos': [
                            {'indice': i, 'error': 'El juez no tiene equipos asignados'}
                            for i in range(len(registros))
                        ]
                    }
                
                # Obtener la competencia del primer equipo
                competencia_juez = equipos.first().competition
                
                # Verificar que la competencia esté en curso
                if not competencia_juez or not competencia_juez.is_running:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros),
                        'registros_guardados': [],
                        'registros_fallidos': [
                            {'indice': i, 'error': 'La competencia no está en curso'}
                            for i in range(len(registros))
                        ]
                    }
                
                # Verificar que el equipo existe y pertenece a este juez
                try:
                    equipo = Equipo.objects.select_for_update().get(id=equipo_id)
                except Equipo.DoesNotExist:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros),
                        'registros_guardados': [],
                        'registros_fallidos': [
                            {'indice': i, 'error': f'El equipo con ID {equipo_id} no existe'}
                            for i in range(len(registros))
                        ]
                    }
                
                if equipo.judge_id != juez.id:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros),
                        'registros_guardados': [],
                        'registros_fallidos': [
                            {'indice': i, 'error': 'El equipo no pertenece al juez'}
                            for i in range(len(registros))
                        ]
                    }
                
                # Contar registros actuales
                num_registros_actuales = RegistroTiempo.objects.filter(team=equipo).count()
                
                # Verificar si el equipo ya tiene registros (evitar envíos duplicados)
                if num_registros_actuales > 0:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros),
                        'registros_guardados': [],
                        'registros_fallidos': [
                            {'indice': i, 'error': f'El equipo ya tiene {num_registros_actuales} registros guardados. No se permiten envíos adicionales.'}
                            for i in range(len(registros))
                        ]
                    }
                
                # Filtrar y normalizar datos válidos
                registros_a_crear = []
                mapping_idx_registro = []  # (indice_original, instancia_registro)
                for idx, reg in enumerate(registros):
                    time = reg.get('tiempo')
                    if time is None:
                        registros_fallidos.append({'indice': idx, 'error': 'Falta el campo tiempo'})
                        continue
                    if num_registros_actuales + len(registros_a_crear) >= self.MAX_REGISTROS_POR_EQUIPO:
                        registros_fallidos.append({'indice': idx, 'error': f'Se alcanzó el límite de {self.MAX_REGISTROS_POR_EQUIPO} registros'})
                        continue
                    record_id = reg.get('id_registro') or uuid.uuid4()
                    registro_obj = RegistroTiempo(
                        record_id=record_id,
                        team=equipo,
                        time=time,
                        hours=reg.get('horas', 0),
                        minutes=reg.get('minutos', 0),
                        seconds=reg.get('segundos', 0),
                        milliseconds=reg.get('milisegundos', 0)
                    )
                    registros_a_crear.append(registro_obj)
                    mapping_idx_registro.append((idx, registro_obj))

                if not registros_a_crear:
                    return {
                        'total_enviados': len(registros),
                        'total_guardados': 0,
                        'total_fallidos': len(registros_fallidos),
                        'registros_guardados': registros_guardados,
                        'registros_fallidos': registros_fallidos,
                    }

                # Crear en bloque con ignore_conflicts para idempotencia
                creados = RegistroTiempo.objects.bulk_create(
                    registros_a_crear,
                    ignore_conflicts=True,
                )

                # Mapear resultados: los no creados son duplicados
                creados_ids = {r.record_id for r in creados}
                for idx, registro_obj in mapping_idx_registro:
                    if registro_obj.record_id in creados_ids:
                        registros_guardados.append({
                            'indice': idx,
                            'id_registro': str(registro_obj.record_id),
                            'tiempo': registro_obj.time,
                            'duplicado': False,
                        })
                    else:
                        registros_guardados.append({
                            'indice': idx,
                            'id_registro': str(registro_obj.record_id),
                            'tiempo': registro_obj.time,
                            'duplicado': True,
                        })

                return {
                    'total_enviados': len(registros),
                    'total_guardados': len(creados),
                    'total_fallidos': len(registros_fallidos),
                    'registros_guardados': registros_guardados,
                    'registros_fallidos': registros_fallidos
                }
                
        except Exception as e:
            return {
                'total_enviados': len(registros),
                'total_guardados': 0,
                'total_fallidos': len(registros),
                'registros_guardados': [],
                'registros_fallidos': [
                    {'indice': i, 'error': f'Error general: {str(e)}'}
                    for i in range(len(registros))
                ]
            }
