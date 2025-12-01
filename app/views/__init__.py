"""
Módulo: views
Contiene todas las vistas de la API organizadas por funcionalidad.
"""

from .auth_views import LoginView, LogoutView, MeView, RefreshTokenView
from .competencia_views import CompetenciaViewSet
from .equipo_views import EquipoViewSet
from .html_views import competencia_list_view, competencia_detail_view, equipo_detail_view
from .admin_views import EstadoCompetenciaAdminView

__all__ = [
    'LoginView',
    'LogoutView',
    'MeView',
    'RefreshTokenView',
    'CompetenciaViewSet',
    'EquipoViewSet',
    'competencia_list_view',
    'competencia_detail_view',
    'equipo_detail_view',
    'EstadoCompetenciaAdminView',
]
