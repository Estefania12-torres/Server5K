from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone

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
        else:
            messages.warning(request, f'La competencia "{competencia.nombre}" ya está en curso.')
        return redirect('admin:app_competencia_changelist')
    
    def detener_competencia_view(self, request, pk):
        competencia = Competencia.objects.get(pk=pk)
        if competencia.detener_competencia():
            messages.success(request, f'La competencia "{competencia.nombre}" ha sido detenida exitosamente.')
        else:
            messages.warning(request, f'La competencia "{competencia.nombre}" no está en curso.')
        return redirect('admin:app_competencia_changelist')

@admin.register(Juez)
class JuezAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'competencia', 'activo']
    list_filter = ['competencia', 'activo']
    search_fields = ['nombre']

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


