"""
Módulo: auth_views
Vistas relacionadas con autenticación y gestión de sesiones.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema
from app.serializers import JuezMeSerializer
from django.db.models import Q

class LoginView(APIView):
    """
    Autenticación de jueces
    
    Endpoint para que los jueces inicien sesión y obtengan tokens JWT.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Iniciar sesión",
        description="Autentica un juez y retorna tokens de acceso (access) y renovación (refresh). Use el endpoint /api/me/ para obtener información del juez.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'juez1'},
                    'password': {'type': 'string', 'example': 'password123'},
                },
                'required': ['username', 'password']
            }
        },
        responses={
            200: {
                'description': 'Login exitoso',
                'content': {
                    'application/json': {
                        'example': {
                            'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                            'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc...'
                        }
                    }
                }
            },
            400: {'description': 'Datos faltantes'},
            401: {'description': 'Credenciales inválidas'},
            403: {'description': 'Usuario inactivo'},
        },
        tags=['Autenticación']
    )
    def post(self, request):
        from app.models import Juez
        from django.contrib.auth.hashers import check_password
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Se requiere username y password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        juez = None
        try:
            juez = Juez.objects.filter(
                is_active=True 
            ).filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()
        except Exception:
            pass  

        if juez:
            password_valid = juez.check_password(password)
        else:
            check_password(password, 'dummy$pbkdf2-sha256$260000$...')
            password_valid = False

        if not juez or not password_valid:
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generar tokens JWT
        refresh = RefreshToken()
        refresh['juez_id'] = juez.id
        refresh['username'] = juez.username
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Se requiere el refresh token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Agregar el refresh token a la blacklist
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {'message': 'Sesión cerrada exitosamente.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except TokenError as e:
            return Response(
                {'error': 'Token inválido o ya fue utilizado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Error al cerrar sesión: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MeView(APIView):
    """
    Información del juez autenticado
    
    Retorna los datos personales del juez que ha iniciado sesión.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Obtener mi información",
        description="Retorna la información personal del juez autenticado (sin credenciales)",
        responses={
            200: JuezMeSerializer,
            401: {'description': 'No autenticado'},
        },
        tags=['Juez']
    )
    def get(self, request):
        """
        Retorna la información personal del juez que ha iniciado sesión.
        No incluye credenciales (username, password) ni información de la competencia.
        """
        juez = request.user
        serializer = JuezMeSerializer(juez)
        
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Refrescar token de acceso",
        description="Genera un nuevo access token usando el refresh token. El refresh token permanece válido.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {'type': 'string', 'example': 'eyJ0eXAiOiJKV1QiLCJhbGc...'},
                },
                'required': ['refresh']
            }
        },
        responses={
            200: {
                'description': 'Token refrescado exitosamente',
                'content': {
                    'application/json': {
                        'example': {
                            'access': 'eyJ0eXAiOiJKV1QiLCJhbGc...',
                            'message': 'Token refrescado exitosamente'
                        }
                    }
                }
            },
            400: {'description': 'Refresh token no proporcionado'},
            401: {'description': 'Refresh token inválido o expirado'},
        },
        tags=['Autenticación']
    )
    def post(self, request):
        from app.models import Juez
        
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Se requiere el refresh token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Crear objeto RefreshToken y obtener nuevo access token
            token = RefreshToken(refresh_token)
            
            # Obtener información del juez del refresh token
            juez_id = token.get('juez_id')
            if juez_id:
                try:
                    juez = Juez.objects.get(id=juez_id, is_active=True)
                    # Agregar claims personalizados al nuevo access token
                    access_token = token.access_token
                    access_token['juez_id'] = juez.id
                    access_token['username'] = juez.username
                    
                    return Response({
                        'access': str(access_token),
                        'message': 'Token refrescado exitosamente'
                    }, status=status.HTTP_200_OK)
                except Juez.DoesNotExist:
                    return Response(
                        {'error': 'Juez no encontrado o inactivo.'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            # Fallback si no hay juez_id en el token
            return Response({
                'access': str(token.access_token),
                'message': 'Token refrescado exitosamente'
            }, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response(
                {'error': 'Refresh token inválido o expirado.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {'error': f'Error al refrescar token: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
