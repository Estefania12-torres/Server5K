from django.db import models

class Juez(models.Model):
    username = models.CharField(max_length=150, unique=True, verbose_name="Usuario")
    password = models.CharField(max_length=128, verbose_name="Contraseña")

    first_name = models.CharField(max_length=150, blank=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Apellido")
    email = models.EmailField(blank=True, verbose_name="Email")

    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Juez"
        verbose_name_plural = "Jueces"

    def __str__(self):
        full_name = self.get_full_name()
        return full_name or self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    @property
    def is_authenticated(self):
        """Indica que el juez está autenticado cuando se usa como 'user'"""
        return True
    
    @property
    def is_anonymous(self):
        """Indica que el juez no es anónimo"""
        return False
