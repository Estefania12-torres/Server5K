"""
Módulo: html_views
Vistas HTML para la interfaz web pública.
"""

from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch
from app.models import Competencia, Equipo, RegistroTiempo
from app.models.equipo import CATEGORIA_CHOICES


def competencia_list_view(request):
    """Listado público de competencias activas."""
    competencias = Competencia.objects.filter(is_active=True).order_by('-datetime')
    return render(request, 'app/competencia_list.html', {'competencias': competencias})


def _procesar_equipos(equipos_queryset):
    """Procesa los equipos y calcula tiempos, posiciones y descalificaciones."""
    equipos_calificados = []
    equipos_descalificados = []
    
    for equipo in equipos_queryset:
        tiempos_competencia = [t for t in equipo.prefetched_tiempos]
        
        # Detectar jugadores ausentes (tiempo = 0 ms)
        jugadores_ausentes = sum(1 for t in tiempos_competencia if t.time == 0)
        equipo.jugadores_ausentes = jugadores_ausentes
        equipo.descalificado = jugadores_ausentes > 0
        
        if tiempos_competencia:
            equipo.tiempo_total_ms = sum(t.time for t in tiempos_competencia)
            equipo.mejor_tiempo_ms = min(t.time for t in tiempos_competencia if t.time > 0) if any(t.time > 0 for t in tiempos_competencia) else 0
            
            # Formatear sin milisegundos
            total_seconds = equipo.tiempo_total_ms // 1000
            s = total_seconds % 60
            total_minutes = total_seconds // 60
            m = total_minutes % 60
            h = total_minutes // 60
            equipo.tiempo_total_formateado = f"{h:02d}:{m:02d}:{s:02d}"
            
            # Mejor tiempo sin milisegundos
            mejor_seconds = equipo.mejor_tiempo_ms // 1000
            mejor_s = mejor_seconds % 60
            mejor_m = (mejor_seconds // 60) % 60
            mejor_h = mejor_seconds // 3600
            equipo.mejor_tiempo_formateado = f"{mejor_h:02d}:{mejor_m:02d}:{mejor_s:02d}"
        else:
            equipo.tiempo_total_ms = 0
            equipo.mejor_tiempo_ms = 0
            equipo.tiempo_total_formateado = "00:00:00"
            equipo.mejor_tiempo_formateado = "00:00:00"
        
        equipo.num_registros = len(equipo.prefetched_tiempos)
        equipo.jugadores_completados = equipo.num_registros - jugadores_ausentes
        
        if equipo.descalificado:
            equipos_descalificados.append(equipo)
        else:
            equipos_calificados.append(equipo)
    
    # Ordenar calificados por tiempo total (menor a mayor)
    equipos_calificados.sort(key=lambda e: e.tiempo_total_ms if e.tiempo_total_ms > 0 else float('inf'))
    equipos_descalificados.sort(key=lambda e: e.tiempo_total_ms)
    
    # Asignar posiciones
    for idx, equipo in enumerate(equipos_calificados, 1):
        equipo.posicion = idx
    
    return equipos_calificados, equipos_descalificados


def competencia_detail_view(request, pk):
    """Detalle de competencia con resultados en tiempo real y filtro por categoría."""
    competencia = get_object_or_404(Competencia, pk=pk, is_active=True)
    
    # Obtener filtro de categoría desde query params
    categoria_filtro = request.GET.get('categoria', '')
    
    # Obtener equipos con tiempos
    tiempos_qs = RegistroTiempo.objects.all().order_by('time')
    equipos_qs = Equipo.objects.filter(
        competition=competencia
    ).select_related('judge').prefetch_related(
        Prefetch('times', queryset=tiempos_qs, to_attr='prefetched_tiempos')
    )
    
    # Aplicar filtro de categoría si existe
    if categoria_filtro:
        equipos_qs = equipos_qs.filter(category=categoria_filtro)
    
    # Procesar equipos
    equipos_calificados, equipos_descalificados = _procesar_equipos(equipos_qs)
    equipos_list = equipos_calificados + equipos_descalificados
    
    # Obtener categorías disponibles en esta competencia
    categorias_disponibles = Equipo.objects.filter(
        competition=competencia
    ).values_list('category', flat=True).distinct()
    
    categorias = [
        {'value': cat[0], 'label': cat[1], 'selected': cat[0] == categoria_filtro}
        for cat in CATEGORIA_CHOICES
        if cat[0] in categorias_disponibles
    ]
    
    return render(request, 'app/competencia_detail.html', {
        'competencia': competencia,
        'equipos': equipos_list,
        'equipos_calificados': len(equipos_calificados),
        'equipos_descalificados': len(equipos_descalificados),
        'en_curso': competencia.is_running,
        'total_equipos': len(equipos_list),
        'categorias': categorias,
        'categoria_filtro': categoria_filtro,
    })


def equipo_detail_view(request, pk):
    """Detalle de un equipo con todos sus registros de tiempo."""
    equipo = get_object_or_404(
        Equipo.objects.select_related('competition', 'judge'),
        pk=pk,
        competition__is_active=True
    )
    
    # Obtener registros ordenados por tiempo
    registros = equipo.times.all().order_by('time')
    
    # Calcular estadísticas
    registros_list = list(registros)
    total_registros = len(registros_list)
    
    if registros_list:
        tiempo_total_ms = sum(r.time for r in registros_list)
        mejor_tiempo_ms = min(r.time for r in registros_list if r.time > 0) if any(r.time > 0 for r in registros_list) else 0
        peor_tiempo_ms = max(r.time for r in registros_list if r.time > 0) if any(r.time > 0 for r in registros_list) else 0
        jugadores_ausentes = sum(1 for r in registros_list if r.time == 0)
    else:
        tiempo_total_ms = 0
        mejor_tiempo_ms = 0
        peor_tiempo_ms = 0
        jugadores_ausentes = 0
    
    def formatear_tiempo(ms):
        if ms == 0:
            return "00:00:00"
        total_seconds = ms // 1000
        s = total_seconds % 60
        total_minutes = total_seconds // 60
        m = total_minutes % 60
        h = total_minutes // 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    # Agregar tiempo formateado a cada registro
    for registro in registros_list:
        registro.tiempo_formateado = formatear_tiempo(registro.time)
    
    return render(request, 'app/equipo_detail.html', {
        'equipo': equipo,
        'competencia': equipo.competition,
        'registros': registros_list,
        'total_registros': total_registros,
        'tiempo_total_ms': tiempo_total_ms,
        'tiempo_total_formateado': formatear_tiempo(tiempo_total_ms),
        'mejor_tiempo_formateado': formatear_tiempo(mejor_tiempo_ms),
        'peor_tiempo_formateado': formatear_tiempo(peor_tiempo_ms),
        'jugadores_ausentes': jugadores_ausentes,
        'jugadores_completados': total_registros - jugadores_ausentes,
    })