"""
Configuración de la aplicación.
"""

from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    verbose_name = 'Sistema de Registro 5K'

    def ready(self):
        """
        Importar signals cuando la app esté lista.
        """
        import app.signals  # noqa
