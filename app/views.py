from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status, viewsets
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .serializers import CompetenciaSerializer, EquipoSerializer, JuezMeSerializer
from .models import Equipo, RegistroTiempo, Juez, Competencia
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch




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
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Se requiere username y password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar el juez por username o email
        try:
            # Intentar buscar por username primero
            try:
                juez = Juez.objects.get(username__iexact=username)
            except Juez.DoesNotExist:
                # Si no existe por username, buscar por email
                juez = Juez.objects.get(email__iexact=username)
        except Juez.DoesNotExist:
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Verificar que el juez esté activo
        if not juez.activo:
            return Response(
                {'error': 'Usuario inactivo. Contacte al administrador.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verificar la contraseña
        if not juez.check_password(password):
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Actualizar last_login
        from django.utils import timezone
        juez.last_login = timezone.now()
        juez.save(update_fields=['last_login'])

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

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Se requiere el refresh token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Crear objeto RefreshToken y obtener nuevo access token
            token = RefreshToken(refresh_token)
            
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


class CompetenciaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para Competencias (solo lectura)
    
    Permite listar todas las competencias y obtener detalles de una competencia específica.
    
    Filtros disponibles:
    - ?activa=true/false - Filtra por competencias activas
    - ?en_curso=true/false - Filtra por competencias en curso
    """
    queryset = Competencia.objects.all().order_by('-fecha_hora')
    serializer_class = CompetenciaSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Listar competencias",
        description="Obtiene todas las competencias con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='activa',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por competencias activas (true/false)',
                required=False,
            ),
            OpenApiParameter(
                name='en_curso',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filtrar por competencias en curso (true/false)',
                required=False,
            ),
        ],
        responses={200: CompetenciaSerializer(many=True)},
        tags=['Competencias']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Obtener competencia",
        description="Obtiene los detalles de una competencia específica por ID",
        responses={
            200: CompetenciaSerializer,
            404: {'description': 'Competencia no encontrada'},
        },
        tags=['Competencias']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def get_queryset(self):
        """
        Permite filtrar competencias por activa y en_curso.
        Solo retorna la competencia del juez autenticado.
        """
        queryset = super().get_queryset()
        
        # Filtrar por la competencia del juez autenticado
        juez = self.request.user
        queryset = queryset.filter(id=juez.competencia_id)
        
        # Filtro por activa
        activa = self.request.query_params.get('activa')
        if activa is not None:
            activa_bool = activa.lower() == 'true'
            queryset = queryset.filter(activa=activa_bool)
        
        # Filtro por en_curso
        en_curso = self.request.query_params.get('en_curso')
        if en_curso is not None:
            en_curso_bool = en_curso.lower() == 'true'
            queryset = queryset.filter(en_curso=en_curso_bool)
        
        return queryset


class EquipoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para Equipos (solo lectura)
    
    Permite listar todos los equipos y obtener detalles de un equipo específico.
    
    Filtros disponibles:
    - ?competencia_id={id} - Filtra equipos por competencia
    - ?juez_id={id} - Filtra equipos por juez asignado
    """
    queryset = Equipo.objects.select_related(
        'juez_asignado',
        'juez_asignado__competencia'
    ).all().order_by('dorsal')
    serializer_class = EquipoSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Listar equipos",
        description="Obtiene todos los equipos con filtros opcionales",
        parameters=[
            OpenApiParameter(
                name='competencia_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de competencia',
                required=False,
            ),
            OpenApiParameter(
                name='juez_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filtrar por ID de juez',
                required=False,
            ),
        ],
        responses={200: EquipoSerializer(many=True)},
        tags=['Equipos']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Obtener equipo",
        description="Obtiene los detalles de un equipo específico por ID",
        responses={
            200: EquipoSerializer,
            404: {'description': 'Equipo no encontrado'},
        },
        tags=['Equipos']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def get_queryset(self):
        """
        Permite filtrar equipos por competencia_id y juez_id.
        Solo retorna los equipos asignados al juez autenticado.
        """
        queryset = super().get_queryset()
        
        # Filtrar por equipos asignados al juez autenticado
        juez = self.request.user
        queryset = queryset.filter(juez_asignado_id=juez.id)
        
        # Filtro por competencia (opcional, ya está filtrado por juez)
        competencia_id = self.request.query_params.get('competencia_id')
        if competencia_id:
            queryset = queryset.filter(juez_asignado__competencia_id=competencia_id)
        
        # Filtro por juez (opcional, redundante pero se mantiene para compatibilidad)
        juez_id = self.request.query_params.get('juez_id')
        if juez_id:
            queryset = queryset.filter(juez_asignado_id=juez_id)
        
        return queryset

# --- Vistas HTML simples para UI local ---------------------------------
def competencia_list_view(request):
    """Listado público de competencias activas (interfaz simple)."""
    competencias = Competencia.objects.filter(activa=True).order_by('-fecha_hora')
    return render(request, 'app/competencia_list.html', {'competencias': competencias})


def competencia_detail_view(request, pk):
    """Detalle de competencia: lista de equipos y sus registros de tiempo."""
    competencia = get_object_or_404(Competencia, pk=pk, activa=True)
    
    # Obtener TODOS los equipos que tienen registros en ESTA competencia
    tiempos_qs = RegistroTiempo.objects.filter(competencia=competencia).order_by('tiempo')
    
    # Obtener IDs de equipos que participaron en esta competencia
    equipos_ids = RegistroTiempo.objects.filter(
        competencia=competencia
    ).values_list('equipo_id', flat=True).distinct()
    
    # Obtener los equipos que participaron
    equipos = Equipo.objects.filter(
        id__in=equipos_ids
    ).select_related('juez_asignado').prefetch_related(
        Prefetch('tiempos', queryset=tiempos_qs, to_attr='prefetched_tiempos')
    )
    
    # Agregar estadísticas a cada equipo
    for equipo in equipos:
        tiempos_competencia = [t for t in equipo.prefetched_tiempos]
        
        if tiempos_competencia:
            equipo.tiempo_total_ms = sum(t.tiempo for t in tiempos_competencia)
            equipo.tiempo_promedio = equipo.tiempo_total_ms // len(tiempos_competencia)
            equipo.mejor_tiempo_ms = tiempos_competencia[0].tiempo  # Ya están ordenados por tiempo ascendente
            
            # Formatear tiempo total
            total_ms = equipo.tiempo_total_ms
            ms = total_ms % 1000
            total_seconds = total_ms // 1000
            s = total_seconds % 60
            total_minutes = total_seconds // 60
            m = total_minutes % 60
            h = total_minutes // 60
            equipo.tiempo_total_formateado = f"{h}h {m}m {s}s {ms}ms"
        else:
            equipo.tiempo_total_ms = 0
            equipo.tiempo_promedio = 0
            equipo.mejor_tiempo_ms = float('inf')  # Infinito para equipos sin tiempos
            equipo.tiempo_total_formateado = "0h 0m 0s 0ms"
        
        equipo.num_registros = len(equipo.prefetched_tiempos)
    
    # Obtener parámetros de ordenamiento
    orden = request.GET.get('orden', 'mejor_tiempo')
    direccion = request.GET.get('dir', 'asc')  # 'asc' o 'desc'
    
    equipos_list = list(equipos)
    
    # Determinar si es orden descendente
    reverse = (direccion == 'desc')
    
    # Ordenamiento basado en parámetro
    if orden == 'tiempo_total':
        equipos_list.sort(key=lambda e: e.tiempo_total_ms, reverse=reverse)
    elif orden == 'promedio':
        equipos_list.sort(key=lambda e: e.tiempo_promedio, reverse=reverse)
    else:  # 'mejor_tiempo' por defecto
        equipos_list.sort(key=lambda e: e.mejor_tiempo_ms, reverse=reverse)
    
    return render(request, 'app/competencia_detail.html', {
        'competencia': competencia,
        'equipos': equipos_list,
    })
