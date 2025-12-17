"""
Módulo: views
Contiene todas las vistas de la API organizadas por funcionalidad.
"""

from .auth_views import LoginView, LogoutView, MeView, RefreshTokenView
from .competencia_views import CompetenciaViewSet
from .equipo_views import EquipoViewSet
from .html_views import competencia_list_view, competencia_detail_view, competencia_results_partial_view, equipo_detail_view
from .admin_views import EstadoCompetenciaAdminView
from .registro_views import RegistrarTiemposView, EstadoEquipoRegistrosView

__all__ = [
    'LoginView',
    'LogoutView',
    'MeView',
    'RefreshTokenView',
    'CompetenciaViewSet',
    'EquipoViewSet',
    'competencia_list_view',
    'competencia_detail_view',
    'competencia_results_partial_view',
    'equipo_detail_view',
    'EstadoCompetenciaAdminView',
    'RegistrarTiemposView',
    'EstadoEquipoRegistrosView',
]
