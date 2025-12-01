from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from app.models import Competencia, Juez, Equipo, RegistroTiempo, ResultadoEquipo

# ======= FILTROS PERSONALIZADOS =======

class EstadoCompetenciaFilter(admin.SimpleListFilter):
    title = 'Estado de la Competencia'
    parameter_name = 'estado'

    def lookups(self, request, model_admin):
        return (
            ('en_curso', '🟢 En Curso'),
            ('finalizada', '⚫ Finalizada'),
            ('programada', '🟠 Programada'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'en_curso':
            return queryset.filter(is_running=True)
        if self.value() == 'finalizada':
            return queryset.filter(is_running=False, finished_at__isnull=False)
        if self.value() == 'programada':
            return queryset.filter(is_running=False, finished_at__isnull=True)
        return queryset

# ======= INLINES =======

class EquipoInline(admin.TabularInline):
    model = Equipo
    extra = 0
    fields = ['number', 'name', 'category', 'judge', 'num_registros_display']
    readonly_fields = ['num_registros_display']

    def num_registros_display(self, obj):
        if obj.pk:
            count = obj.times.count()
            return format_html('<b>{}</b> registros', count)
        return '-'
    num_registros_display.short_description = 'Registros'

class RegistroTiempoInline(admin.TabularInline):
    model = RegistroTiempo
    extra = 0
    fields = ['tiempo_formateado_display', 'created_at']
    readonly_fields = ['tiempo_formateado_display', 'created_at']
    can_delete = True
    ordering = ['time']

    def tiempo_formateado_display(self, obj):
        if obj.pk:
            return format_html(
                '<b>{}h {}m {}s {}ms</b>',
                obj.hours, obj.minutes, obj.seconds, obj.milliseconds
            )
        return '-'
    tiempo_formateado_display.short_description = 'Tiempo'

# ======= ADMIN MODELS =======

@admin.register(Competencia)
class CompetenciaAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'datetime',
        'get_status_display',
        'total_equipos',
        'total_registros',
        'is_active',
        'acciones_competencia',
    ]
    list_filter = [EstadoCompetenciaFilter, 'is_active']
    search_fields = ['name']
    readonly_fields = ['started_at', 'finished_at']
    list_per_page = 25
    actions = ['iniciar_competencia', 'detener_competencia']
    
    # Template personalizado para incluir cronómetro
    change_list_template = 'admin/app/competencia/change_list.html'

    fieldsets = (
        ('Información General', {
            'fields': ('name', 'datetime', 'is_active')
        }),
        ('Estado de la Competencia', {
            'fields': ('is_running', 'started_at', 'finished_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [EquipoInline]

    def total_equipos(self, obj):
        return obj.teams.count()
    total_equipos.short_description = 'Equipos'

    def total_registros(self, obj):
        # Suma registros de todos los equipos en esta competencia
        return RegistroTiempo.objects.filter(team__competition=obj).count()
    total_registros.short_description = 'Registros de Tiempo'

    def get_status_display(self, obj):
        """Muestra el estado con cronómetro inline si está en curso"""
        if obj.is_running:
            # Incluir cronómetro inline cuando está en curso
            started_at_iso = obj.started_at.isoformat() if obj.started_at else ''
            return format_html(
                '<div style="display: flex; align-items: center; gap: 10px;">'
                '<span style="padding: 6px 12px; background-color: #28a745; color: white; '
                'border-radius: 20px; font-weight: bold; font-size: 11px; '
                'text-transform: uppercase; letter-spacing: 0.5px;">'
                '🏁 EN CURSO</span>'
                '<span class="cronometro-inline" data-started-at="{}" '
                'style="font-family: \'Courier New\', monospace; font-size: 16px; '
                'font-weight: bold; color: #28a745; background: #f0f0f0; padding: 4px 10px; '
                'border-radius: 5px; min-width: 100px; text-align: center;">00:00:00</span>'
                '</div>',
                started_at_iso
            )
        elif obj.finished_at:
            return format_html(
                '<span style="padding: 6px 12px; background-color: #6c757d; color: white; '
                'border-radius: 20px; font-weight: bold; font-size: 11px; '
                'text-transform: uppercase; letter-spacing: 0.5px;">'
                '⏹️ FINALIZADA</span>'
            )
        else:
            return format_html(
                '<span style="padding: 6px 12px; background-color: #ffc107; color: #000; '
                'border-radius: 20px; font-weight: bold; font-size: 11px; '
                'text-transform: uppercase; letter-spacing: 0.5px;">'
                '🕒 PROGRAMADA</span>'
            )
    
    get_status_display.short_description = 'Estado'

    def acciones_competencia(self, obj):
        """Muestra botones de acción para iniciar/detener la competencia"""
        from django.urls import reverse
        from django.utils.html import format_html
        
        if obj.is_running:
            # Botón para detener (rojo)
            url = reverse('admin:app_competencia_detener', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" onclick="return confirm(\'¿Estás seguro de detener esta competencia?\');" '
                'style="background-color: #dc3545; color: white; padding: 6px 12px; '
                'text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; '
                'display: inline-block; border: none; cursor: pointer;">'
                '⏹️ Detener</a>',
                url
            )
        else:
            # Botón para iniciar (verde)
            url = reverse('admin:app_competencia_iniciar', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" onclick="return confirm(\'¿Iniciar la competencia {}?\');" '
                'style="background-color: #28a745; color: white; padding: 6px 12px; '
                'text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; '
                'display: inline-block; border: none; cursor: pointer;">'
                '🟢 Iniciar</a>',
                url, obj.name
            )
    
    acciones_competencia.short_description = 'Acciones'
    acciones_competencia.allow_tags = True

    def iniciar_competencia(self, request, queryset):
        """Acción personalizada para iniciar competencia (solo una a la vez)"""
        if queryset.count() > 1:
            self.message_user(request, "⚠️ Solo puedes iniciar una competencia a la vez", level='error')
            return
        
        competencia = queryset.first()
        resultado = competencia.start()
        
        if resultado['success']:
            self.message_user(request, f"✅ Competencia '{competencia.name}' iniciada correctamente.")
        elif resultado['message'] == 'already_running':
            self.message_user(
                request, 
                f"⚠️ La competencia '{competencia.name}' ya está en curso", 
                level='warning'
            )
        elif resultado['message'] == 'another_running':
            otra = resultado['competencia']
            self.message_user(
                request,
                f"❌ No se puede iniciar '{competencia.name}'. La competencia '{otra.name}' ya está en curso. "
                f"Primero debes detener la competencia activa desde el administrador.",
                level='error'
            )
    
    iniciar_competencia.short_description = "🟢 Iniciar competencia seleccionada"

    def detener_competencia(self, request, queryset):
        """Acción personalizada para detener competencia"""
        count = 0
        for competencia in queryset:
            resultado = competencia.stop()
            if resultado['success']:
                count += 1
        
        if count > 0:
            self.message_user(request, f"✅ {count} competencia(s) detenida(s) correctamente")
        else:
            self.message_user(request, "⚠️ Las competencias seleccionadas no estaban en curso", level='warning')
    
    detener_competencia.short_description = "⏹️ Detener competencia(s) seleccionada(s)"

    def get_urls(self):
        """Agrega URLs personalizadas para los botones de acción"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:competencia_id>/iniciar/',
                self.admin_site.admin_view(self.iniciar_competencia_view),
                name='app_competencia_iniciar',
            ),
            path(
                '<int:competencia_id>/detener/',
                self.admin_site.admin_view(self.detener_competencia_view),
                name='app_competencia_detener',
            ),
        ]
        return custom_urls + urls

    def iniciar_competencia_view(self, request, competencia_id):
        """Vista para iniciar una competencia desde el botón"""
        try:
            competencia = Competencia.objects.get(pk=competencia_id)
            resultado = competencia.start()
            
            if resultado['success']:
                messages.success(request, f"✅ Competencia '{competencia.name}' iniciada correctamente.")
            elif resultado['message'] == 'already_running':
                messages.warning(request, f"⚠️ La competencia '{competencia.name}' ya está en curso.")
            elif resultado['message'] == 'another_running':
                otra = resultado['competencia']
                messages.error(
                    request,
                    f"❌ No se puede iniciar '{competencia.name}'. La competencia '{otra.name}' ya está en curso. "
                    f"Primero debes detener la competencia activa."
                )
        except Competencia.DoesNotExist:
            messages.error(request, "❌ La competencia no existe.")
        
        return redirect('admin:app_competencia_changelist')

    def detener_competencia_view(self, request, competencia_id):
        """Vista para detener una competencia desde el botón"""
        try:
            competencia = Competencia.objects.get(pk=competencia_id)
            resultado = competencia.stop()
            
            if resultado['success']:
                messages.success(request, f"✅ Competencia '{competencia.name}' detenida correctamente.")
            else:
                messages.warning(request, f"⚠️ La competencia '{competencia.name}' no estaba en curso.")
        except Competencia.DoesNotExist:
            messages.error(request, "❌ La competencia no existe.")
        
        return redirect('admin:app_competencia_changelist')


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['number', 'name', 'category', 'competition', 'judge', 'num_registros', 'ver_resultados']
    list_filter = ['competition', 'category', 'judge']
    search_fields = ['name', 'number']
    inlines = [RegistroTiempoInline]
    list_select_related = ['competition', 'judge']

    def num_registros(self, obj):
        return obj.times.count()
    num_registros.short_description = 'Registros'

    def ver_resultados(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:app_resultadoequipo_change', args=[obj.pk])
        return format_html('<a href="{}" class="button">Ver Resultados</a>', url)
    ver_resultados.short_description = 'Resultados'
    ver_resultados.allow_tags = True


@admin.register(Juez)
class JuezAdmin(admin.ModelAdmin):
    list_display = ['username', 'get_full_name', 'email', 'equipos_asignados', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']

    def equipos_asignados(self, obj):
        equipos = obj.teams.all()
        if equipos:
            return ', '.join([str(e.number) for e in equipos])
        return '-'
    equipos_asignados.short_description = 'Equipos'


@admin.register(RegistroTiempo)
class RegistroTiempoAdmin(admin.ModelAdmin):
    list_display = [
        'id_registro_corto', 
        'equipo_con_dorsal', 
        'competencia_display',
        'tiempo_formateado_display', 
        'created_at'
    ]
    list_filter = ['team__competition']
    search_fields = ['team__name']
    ordering = ['time']
    readonly_fields = ['record_id', 'team', 'time', 'hours', 'minutes', 'seconds', 'milliseconds', 'created_at']

    def id_registro_corto(self, obj):
        return str(obj.record_id)[:8]
    id_registro_corto.short_description = 'ID'

    def equipo_con_dorsal(self, obj):
        return f"{obj.team.number} {obj.team.name}"
    equipo_con_dorsal.short_description = 'Equipo'
    equipo_con_dorsal.admin_order_field = 'team__number'

    def competencia_display(self, obj):
        return obj.team.competition
    competencia_display.short_description = 'Competencia'
    competencia_display.admin_order_field = 'team__competition'

    def tiempo_formateado_display(self, obj):
        return f"{obj.hours}h {obj.minutes}m {obj.seconds}s {obj.milliseconds}ms"
    tiempo_formateado_display.short_description = 'Tiempo'


@admin.register(ResultadoEquipo)
class ResultadoEquipoAdmin(admin.ModelAdmin):
    list_display = ['number', 'name', 'competition', 'tiempo_total_display', 'num_registros']
    list_filter = ['competition']
    search_fields = ['name', 'number']
    inlines = [RegistroTiempoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('times')

    def num_registros(self, obj):
        return obj.times.count()
    num_registros.short_description = 'Nº Registros'
    
    def tiempo_total_display(self, obj):
        total = obj.total_time()
        if total:
            hours = total // 3600000
            minutes = (total % 3600000) // 60000
            seconds = (total % 60000) // 1000
            milliseconds = total % 1000
            return f"{hours}h {minutes}m {seconds}s {milliseconds}ms"
        return '-'
    tiempo_total_display.short_description = 'Tiempo Total'
