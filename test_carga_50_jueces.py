"""
Script de prueba de carga para simular 50+ jueces simultáneos.

Este script:
1. Crea 50 jueces con equipos asignados (si no existen)
2. Simula login simultáneo de todos los jueces
3. Conecta WebSocket para cada juez
4. Envía 15 registros por equipo (simulando el flujo real)
5. Mide tiempos de respuesta y errores

Uso:
    uv run python test_carga_50_jueces.py

Requisitos:
    - Servidor corriendo en localhost:8000
    - Redis corriendo en localhost:6379
    - PostgreSQL configurado (o SQLite para pruebas básicas)
"""

import asyncio
import aiohttp
import time
import random
import uuid
import statistics
from dataclasses import dataclass, field
from typing import List, Optional
import json

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
NUM_JUECES = 50  # Número de jueces a simular
REGISTROS_POR_EQUIPO = 15
TIMEOUT_SEGUNDOS = 30

# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class ResultadoJuez:
    juez_id: int
    username: str
    login_ok: bool = False
    login_tiempo_ms: float = 0
    ws_conectado: bool = False
    ws_tiempo_ms: float = 0
    registros_enviados: bool = False
    registros_tiempo_ms: float = 0
    error: Optional[str] = None


@dataclass
class ResultadosPrueba:
    total_jueces: int = 0
    login_exitosos: int = 0
    ws_exitosos: int = 0
    registros_exitosos: int = 0
    errores: List[str] = field(default_factory=list)
    tiempos_login: List[float] = field(default_factory=list)
    tiempos_ws: List[float] = field(default_factory=list)
    tiempos_registros: List[float] = field(default_factory=list)
    tiempo_total: float = 0


# ============================================================================
# FUNCIONES DE PRUEBA
# ============================================================================

async def login_juez(session: aiohttp.ClientSession, username: str, password: str) -> tuple[Optional[str], float]:
    """Realiza login y retorna (token, tiempo_ms) o (None, tiempo_ms) si falla."""
    inicio = time.perf_counter()
    try:
        async with session.post(
            f"{BASE_URL}/api/login/",
            json={"username": username, "password": password},
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEGUNDOS)
        ) as resp:
            tiempo_ms = (time.perf_counter() - inicio) * 1000
            if resp.status == 200:
                data = await resp.json()
                return data.get("access"), tiempo_ms
            else:
                return None, tiempo_ms
    except Exception as e:
        tiempo_ms = (time.perf_counter() - inicio) * 1000
        return None, tiempo_ms


async def obtener_equipo(session: aiohttp.ClientSession, token: str) -> Optional[dict]:
    """Obtiene el primer equipo asignado al juez."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with session.get(
            f"{BASE_URL}/api/equipos/",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEGUNDOS)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                equipos = data if isinstance(data, list) else data.get("results", [])
                return equipos[0] if equipos else None
            return None
    except Exception:
        return None


async def conectar_websocket(session: aiohttp.ClientSession, juez_id: int, token: str) -> tuple[bool, float]:
    """Conecta al WebSocket y retorna (éxito, tiempo_ms)."""
    inicio = time.perf_counter()
    try:
        ws_url = f"{WS_URL}/ws/juez/{juez_id}/?token={token}"
        async with session.ws_connect(ws_url, timeout=TIMEOUT_SEGUNDOS) as ws:
            tiempo_ms = (time.perf_counter() - inicio) * 1000
            # Esperar un momento para confirmar conexión estable
            await asyncio.sleep(0.1)
            await ws.close()
            return True, tiempo_ms
    except Exception as e:
        tiempo_ms = (time.perf_counter() - inicio) * 1000
        return False, tiempo_ms


async def enviar_registros(session: aiohttp.ClientSession, token: str, equipo_id: int) -> tuple[bool, float]:
    """Envía 15 registros y retorna (éxito, tiempo_ms)."""
    inicio = time.perf_counter()
    try:
        # Generar 15 registros simulados
        registros = []
        for i in range(REGISTROS_POR_EQUIPO):
            tiempo_base = random.randint(300000, 1800000)  # 5-30 minutos en ms
            registros.append({
                "id_registro": str(uuid.uuid4()),
                "tiempo": tiempo_base + (i * 1000),  # Incrementar 1 seg por registro
                "horas": 0,
                "minutos": tiempo_base // 60000,
                "segundos": (tiempo_base // 1000) % 60,
                "milisegundos": tiempo_base % 1000,
            })
        
        headers = {"Authorization": f"Bearer {token}"}
        async with session.post(
            f"{BASE_URL}/api/equipos/{equipo_id}/registros/",
            json={"registros": registros},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEGUNDOS)
        ) as resp:
            tiempo_ms = (time.perf_counter() - inicio) * 1000
            if resp.status == 201:
                return True, tiempo_ms
            else:
                return False, tiempo_ms
    except Exception as e:
        tiempo_ms = (time.perf_counter() - inicio) * 1000
        return False, tiempo_ms


async def simular_juez(session: aiohttp.ClientSession, juez_num: int) -> ResultadoJuez:
    """Simula el flujo completo de un juez."""
    username = f"juez{juez_num}"
    password = f"juez{juez_num}123"  # Password del populate_data: juez1123, juez2123, etc.
    
    resultado = ResultadoJuez(juez_id=juez_num, username=username)
    
    # 1. Login
    token, tiempo = await login_juez(session, username, password)
    resultado.login_tiempo_ms = tiempo
    if not token:
        resultado.error = "Login fallido"
        return resultado
    resultado.login_ok = True
    
    # 2. Obtener equipo asignado
    equipo = await obtener_equipo(session, token)
    if not equipo:
        resultado.error = "No tiene equipo asignado"
        return resultado
    
    # 3. Conectar WebSocket
    ws_ok, tiempo = await conectar_websocket(session, juez_num, token)
    resultado.ws_tiempo_ms = tiempo
    resultado.ws_conectado = ws_ok
    
    # 4. Enviar registros
    reg_ok, tiempo = await enviar_registros(session, token, equipo["id"])
    resultado.registros_tiempo_ms = tiempo
    resultado.registros_enviados = reg_ok
    
    if not reg_ok:
        resultado.error = "Error enviando registros"
    
    return resultado


async def ejecutar_prueba_carga():
    """Ejecuta la prueba de carga con todos los jueces."""
    print("\n" + "=" * 70)
    print("🚀 PRUEBA DE CARGA - 50 JUECES SIMULTÁNEOS")
    print("=" * 70)
    print(f"\n📋 Configuración:")
    print(f"   - Jueces a simular: {NUM_JUECES}")
    print(f"   - Registros por equipo: {REGISTROS_POR_EQUIPO}")
    print(f"   - Servidor: {BASE_URL}")
    print(f"   - Timeout: {TIMEOUT_SEGUNDOS}s")
    
    # Verificar que el servidor esté corriendo
    print(f"\n🔍 Verificando servidor...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status in [200, 404]:
                    print("   ✅ Servidor accesible")
                else:
                    print(f"   ⚠️ Servidor respondió con status {resp.status}")
    except Exception as e:
        print(f"   ❌ Error conectando al servidor: {e}")
        print("\n⚠️ Asegúrate de que el servidor esté corriendo con:")
        print("   .\\start_server_lan.ps1")
        return
    
    # Ejecutar prueba
    print(f"\n⏱️ Iniciando prueba de carga...")
    inicio_total = time.perf_counter()
    
    resultados = ResultadosPrueba(total_jueces=NUM_JUECES)
    
    # Crear sesión compartida con pool de conexiones
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Ejecutar todos los jueces en paralelo
        tareas = [simular_juez(session, i + 1) for i in range(NUM_JUECES)]
        
        # Mostrar progreso
        print(f"\n   Ejecutando {NUM_JUECES} jueces en paralelo...")
        
        resultados_jueces = await asyncio.gather(*tareas, return_exceptions=True)
    
    resultados.tiempo_total = (time.perf_counter() - inicio_total) * 1000
    
    # Procesar resultados
    for r in resultados_jueces:
        if isinstance(r, Exception):
            resultados.errores.append(str(r))
            continue
        
        if r.login_ok:
            resultados.login_exitosos += 1
            resultados.tiempos_login.append(r.login_tiempo_ms)
        
        if r.ws_conectado:
            resultados.ws_exitosos += 1
            resultados.tiempos_ws.append(r.ws_tiempo_ms)
        
        if r.registros_enviados:
            resultados.registros_exitosos += 1
            resultados.tiempos_registros.append(r.registros_tiempo_ms)
        
        if r.error:
            resultados.errores.append(f"{r.username}: {r.error}")
    
    # Mostrar resultados
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DE LA PRUEBA")
    print("=" * 70)
    
    print(f"\n✅ ÉXITOS:")
    print(f"   Login:     {resultados.login_exitosos}/{NUM_JUECES} ({resultados.login_exitosos*100//NUM_JUECES}%)")
    print(f"   WebSocket: {resultados.ws_exitosos}/{NUM_JUECES} ({resultados.ws_exitosos*100//NUM_JUECES}%)")
    print(f"   Registros: {resultados.registros_exitosos}/{NUM_JUECES} ({resultados.registros_exitosos*100//NUM_JUECES}%)")
    
    print(f"\n⏱️ TIEMPOS DE RESPUESTA:")
    if resultados.tiempos_login:
        print(f"   Login:")
        print(f"      Promedio: {statistics.mean(resultados.tiempos_login):.0f}ms")
        print(f"      Mínimo:   {min(resultados.tiempos_login):.0f}ms")
        print(f"      Máximo:   {max(resultados.tiempos_login):.0f}ms")
    
    if resultados.tiempos_ws:
        print(f"   WebSocket:")
        print(f"      Promedio: {statistics.mean(resultados.tiempos_ws):.0f}ms")
        print(f"      Mínimo:   {min(resultados.tiempos_ws):.0f}ms")
        print(f"      Máximo:   {max(resultados.tiempos_ws):.0f}ms")
    
    if resultados.tiempos_registros:
        print(f"   Registros (15 por equipo):")
        print(f"      Promedio: {statistics.mean(resultados.tiempos_registros):.0f}ms")
        print(f"      Mínimo:   {min(resultados.tiempos_registros):.0f}ms")
        print(f"      Máximo:   {max(resultados.tiempos_registros):.0f}ms")
    
    print(f"\n⏱️ TIEMPO TOTAL: {resultados.tiempo_total/1000:.2f} segundos")
    
    if resultados.errores:
        print(f"\n❌ ERRORES ({len(resultados.errores)}):")
        for error in resultados.errores[:10]:  # Mostrar solo los primeros 10
            print(f"   - {error}")
        if len(resultados.errores) > 10:
            print(f"   ... y {len(resultados.errores) - 10} errores más")
    
    # Veredicto
    print("\n" + "=" * 70)
    tasa_exito = resultados.registros_exitosos * 100 // NUM_JUECES if NUM_JUECES > 0 else 0
    if tasa_exito >= 95:
        print("🎉 VEREDICTO: ✅ SISTEMA LISTO PARA 50+ DISPOSITIVOS")
    elif tasa_exito >= 80:
        print("⚠️ VEREDICTO: SISTEMA FUNCIONAL PERO CON ALGUNOS FALLOS")
    else:
        print("❌ VEREDICTO: SISTEMA NO SOPORTA LA CARGA REQUERIDA")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(ejecutar_prueba_carga())
