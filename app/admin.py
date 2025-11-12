from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django import forms

from .models import Competencia, Juez, Equipo, RegistroTiempo

@admin.register(Competencia)
class CompetenciaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha_hora', 'categoria', 'estado_competencia', 'activa', 'acciones_competencia']
    list_filter = ['categoria', 'activa', 'en_curso']
    search_fields = ['nombre']
    readonly_fields = ['fecha_inicio', 'fecha_fin']
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'fecha_hora', 'categoria', 'activa')
        }),
        ('Estado de la Competencia', {
            'fields': ('en_curso', 'fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',)
        }),
    )
    
    def estado_competencia(self, obj):
        if obj.en_curso:
            return format_html('<span style="color: green; font-weight: bold;">🟢 EN CURSO</span>')
        elif obj.fecha_fin:
            return format_html('<span style="color: gray;">⚫ FINALIZADA</span>')
        else:
            return format_html('<span style="color: orange;">🟠 NO INICIADA</span>')
    estado_competencia.short_description = 'Estado'
    
    def acciones_competencia(self, obj):
        if obj.en_curso:
            return format_html(
                '<a class="button" href="{}">🛑 Detener</a>',
                f'/admin/app/competencia/{obj.pk}/detener/'
            )
        else:
            return format_html(
                '<a class="button" href="{}">▶️ Iniciar</a>',
                f'/admin/app/competencia/{obj.pk}/iniciar/'
            )
    acciones_competencia.short_description = 'Acciones'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/iniciar/', self.admin_site.admin_view(self.iniciar_competencia_view), name='iniciar-competencia'),
            path('<int:pk>/detener/', self.admin_site.admin_view(self.detener_competencia_view), name='detener-competencia'),
        ]
        return custom_urls + urls
    
    def iniciar_competencia_view(self, request, pk):
        competencia = Competencia.objects.get(pk=pk)
        if competencia.iniciar_competencia():
            messages.success(request, f'La competencia "{competencia.nombre}" ha sido iniciada exitosamente.')
            # Notify jueces via channels
            channel_layer = get_channel_layer()
            for juez in competencia.jueces.all():
                group = f'juez_{juez.id}'
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'competencia.iniciada',
                        'data': {
                            'mensaje': 'La competencia ha iniciado. Ya puedes registrar tiempos.',
                            'competencia_id': competencia.id,
                            'competencia_nombre': competencia.nombre,
                            'en_curso': True,
                        }
                    }
                )
        else:
            messages.warning(request, f'La competencia "{competencia.nombre}" ya está en curso.')
        return redirect('admin:app_competencia_changelist')
    
    def detener_competencia_view(self, request, pk):
        competencia = Competencia.objects.get(pk=pk)
        if competencia.detener_competencia():
            messages.success(request, f'La competencia "{competencia.nombre}" ha sido detenida exitosamente.')
            # Notify jueces via channels
            channel_layer = get_channel_layer()
            for juez in competencia.jueces.all():
                group = f'juez_{juez.id}'
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'competencia.detenida',
                        'data': {
                            'mensaje': 'La competencia ha finalizado. No se pueden registrar más tiempos.',
                            'competencia_id': competencia.id,
                            'competencia_nombre': competencia.nombre,
                            'en_curso': False,
                        }
                    }
                )
        else:
            messages.warning(request, f'La competencia "{competencia.nombre}" no está en curso.')
        return redirect('admin:app_competencia_changelist')

class JuezForm(forms.ModelForm):
    """Formulario personalizado para crear/editar jueces"""
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = Juez
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'competencia', 'activo']
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Si es un nuevo juez, la contraseña es requerida
        if not self.instance.pk and not password1:
            raise forms.ValidationError('La contraseña es requerida para nuevos jueces.')
        
        # Si se proporciona contraseña, deben coincidir
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        
        return cleaned_data
    
    def save(self, commit=True):
        juez = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        
        if password:
            juez.set_password(password)
        
        if commit:
            juez.save()
        return juez

@admin.register(Juez)
class JuezAdmin(admin.ModelAdmin):
    """
    Admin para el modelo Juez.
    Los jueces NO son usuarios de Django, tienen su propio modelo.
    """
    form = JuezForm
    list_display = ['username', 'get_full_name', 'email', 'competencia', 'activo', 'fecha_creacion']
    list_filter = ['competencia', 'activo', 'fecha_creacion']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['-fecha_creacion']
    readonly_fields = ['fecha_creacion', 'last_login']
    
    fieldsets = (
        ('Credenciales de Acceso', {
            'fields': ('username', 'password1', 'password2')
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email', 'telefono')
        }),
        ('Información del Juez', {
            'fields': ('competencia', 'activo'),
        }),
        ('Información del Sistema', {
            'fields': ('fecha_creacion', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
    get_full_name.short_description = 'Nombre Completo'

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'dorsal', 'juez_asignado', 'competencia']
    list_filter = ['juez_asignado__competencia']
    search_fields = ['nombre', 'dorsal']
    ordering = ['dorsal']

@admin.register(RegistroTiempo)
class RegistroTiempoAdmin(admin.ModelAdmin):
    list_display = ['id_registro', 'equipo', 'tiempo_formateado', 'timestamp']
    list_filter = ['equipo__juez_asignado__competencia', 'timestamp']
    search_fields = ['id_registro', 'equipo__nombre']
    readonly_fields = ['id_registro', 'timestamp']
    
    def tiempo_formateado(self, obj):
        segundos = obj.tiempo / 1000
        minutos = int(segundos // 60)
        segs = segundos % 60
        return f"{minutos}:{segs:.3f}"
    tiempo_formateado.short_description = 'Tiempo'


