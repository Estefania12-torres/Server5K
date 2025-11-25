"""
Módulo: validators
Funciones de validación para conexiones WebSocket y mensajes entrantes.
"""

import logging
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_juez_from_token(token):
    """
    Valida el token JWT y retorna el juez.
    
    Args:
        token: Token JWT de acceso
        
    Returns:
        Juez instance si es válido, None en caso contrario
    """
    from app.models import Juez
    
    try:
        logger.debug(f"🔍 Validando token JWT...")
        # Validar el token
        access_token = AccessToken(token)
        juez_id = access_token.get('juez_id')
        
        logger.debug(f"🔍 Token decodificado - juez_id: {juez_id}")
        
        if not juez_id:
            logger.error("❌ Token no contiene juez_id")
            return None
        
        # Obtener el juez con sus equipos (prefetch_related para optimizar)
        juez = Juez.objects.prefetch_related('teams', 'teams__competition').get(id=juez_id, is_active=True)
        logger.info(f"✅ Juez encontrado: {juez.username} (ID: {juez.id})")
        return juez
    except Juez.DoesNotExist:
        logger.error(f"❌ Juez con ID {juez_id} no existe o está inactivo")
        return None
    except Exception as e:
        logger.error(f"❌ Error validando token: {e}")
        return None


@database_sync_to_async
def verificar_competencia_activa(juez):
    """
    Verifica que el juez tenga una competencia activa.
    
    Args:
        juez: Instancia del modelo Juez
        
    Returns:
        bool: True si la competencia está activa, False en caso contrario
    """
    tiene_competencia = juez.teams.filter(competition__is_active=True).exists()
    logger.debug(f"🔍 Juez {juez.id} tiene competencia activa: {tiene_competencia}")
    return tiene_competencia


@database_sync_to_async
def verificar_competencia_en_curso(juez):
    """
    Verifica que la competencia del juez esté en curso.
    
    Args:
        juez: Instancia del modelo Juez
        
    Returns:
        bool: True si la competencia está en curso, False en caso contrario
    """
    return juez.teams.filter(competition__is_running=True).exists()


@database_sync_to_async
def obtener_estado_competencia(juez):
    """
    Obtiene el estado de la competencia del juez.
    
    Args:
        juez: Instancia del modelo Juez
        
    Returns:
        dict: Diccionario con información de la competencia o None si no existe
    """
    equipo = juez.teams.select_related('competition').filter(competition__is_active=True).first()
    if not equipo or not equipo.competition:
        return None
    
    competencia = equipo.competition
    
    return {
        'id': competencia.id,
        'nombre': competencia.name,
        'en_curso': competencia.is_running,
        'activa': competencia.is_active,
    }


@database_sync_to_async
def validar_equipo_pertenece_juez(equipo_id, juez_id):
    """
    Valida que un equipo pertenezca al juez especificado.
    
    Args:
        equipo_id: ID del equipo
        juez_id: ID del juez
        
    Returns:
        bool: True si el equipo pertenece al juez, False en caso contrario
    """
    from app.models import Equipo
    
    try:
        equipo = Equipo.objects.get(id=equipo_id)
        return equipo.judge_id == juez_id
    except Equipo.DoesNotExist:
        return False


def validar_datos_registro(content):
    """
    Valida que los datos de un registro de tiempo sean correctos.
    
    Args:
        content: Diccionario con los datos del registro
        
    Returns:
        tuple: (bool_valido, mensaje_error)
    """
    equipo_id = content.get('equipo_id')
    tiempo = content.get('tiempo')
    
    if equipo_id is None:
        return False, 'Falta el campo equipo_id'
    
    if tiempo is None:
        return False, 'Falta el campo tiempo'
    
    if not isinstance(tiempo, (int, float)) or tiempo < 0:
        return False, 'El tiempo debe ser un número positivo'
    
    return True, None


def validar_datos_batch(content):
    """
    Valida que los datos de un batch de registros sean correctos.
    
    Args:
        content: Diccionario con los datos del batch
        
    Returns:
        tuple: (bool_valido, mensaje_error)
    """
    equipo_id = content.get('equipo_id')
    registros = content.get('registros', [])
    
    if equipo_id is None:
        return False, 'Falta el campo equipo_id'
    
    if not registros or not isinstance(registros, list):
        return False, 'Faltan los registros o no es una lista válida'
    
    if len(registros) > 15:
        return False, 'El batch no puede contener más de 15 registros'
    
    return True, None
