"""
Backend de autenticación personalizado para Jueces.
Los jueces NO son usuarios de Django, tienen su propio modelo.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from app.models import Juez


class JuezJWTAuthentication(JWTAuthentication):
    """
    Autenticación JWT personalizada para el modelo Juez.
    """
    
    def get_user(self, validated_token):
        """
        Obtiene el juez desde el token JWT validado.
        """
        try:
            juez_id = validated_token.get('juez_id')
            if juez_id is None:
                raise InvalidToken('Token no contiene juez_id')
            
            juez = Juez.objects.get(id=juez_id, is_active=True)
            return juez
        except Juez.DoesNotExist:
            raise InvalidToken('Juez no encontrado o inactivo')
