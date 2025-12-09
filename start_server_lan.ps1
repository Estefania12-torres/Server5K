# ============================================================================
# Script de inicio Server5K para pruebas en Red LAN Local
# ============================================================================
# Configurado para: IP 192.168.0.108
# Redis: Docker container redis-dev (puerto 6379)
# Uso: .\start_server_lan.ps1
# ============================================================================

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  🚀 Server5K - Modo Pruebas LAN" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 1. Verificar Redis en Docker
# ============================================================================
Write-Host "📡 [1/7] Verificando Redis en Docker..." -ForegroundColor Cyan

$redisContainer = docker ps --filter "name=redis-dev" --format "{{.Names}}" 2>$null
if ($redisContainer -eq "redis-dev") {
    Write-Host "   ✅ Container 'redis-dev' está corriendo" -ForegroundColor Green
    
    # Verificar conectividad con Redis
    $redisPing = redis-cli ping 2>$null
    if ($redisPing -eq "PONG") {
        Write-Host "   ✅ Redis responde correctamente (PONG)" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  Redis no responde al comando ping" -ForegroundColor Yellow
        Write-Host "   Verifica que redis-cli esté instalado o ejecuta: docker exec redis-dev redis-cli ping" -ForegroundColor Gray
    }
}
else {
    Write-Host "   ❌ Container 'redis-dev' no encontrado o no está corriendo" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Para iniciar Redis en Docker, ejecuta:" -ForegroundColor Yellow
    Write-Host "   docker start redis-dev" -ForegroundColor White
    Write-Host ""
    Write-Host "   Si no existe el container, créalo con:" -ForegroundColor Yellow
    Write-Host "   docker run -d --name redis-dev -p 6379:6379 redis:latest" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host ""

# ============================================================================
# 2. Verificar Postgres en Docker (docker-compose)
# ============================================================================
Write-Host "🗄️  [2/7] Verificando Postgres en Docker..." -ForegroundColor Cyan

$pgContainer = docker ps --filter "name=server5k-postgres" --format "{{.Names}}" 2>$null
if ($pgContainer -eq "server5k-postgres") {
    Write-Host "   ✅ Container 'server5k-postgres' está corriendo" -ForegroundColor Green
}
else {
    Write-Host "   ⚠️  Postgres no está corriendo, levantando con docker-compose" -ForegroundColor Yellow
    docker compose up -d postgres
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ❌ No se pudo levantar Postgres con docker-compose" -ForegroundColor Red
        exit 1
    }
    else {
        Write-Host "   ✅ Postgres iniciado" -ForegroundColor Green
    }
}

Write-Host ""

# ============================================================================
# 3. Obtener y mostrar IP Local
# ============================================================================
Write-Host "🌐 [3/7] Verificando configuración de red..." -ForegroundColor Cyan

# $ipAddress = "192.168.0.190"  # IP configurada en ALLOWED_HOSTS
$ipAddress = "192.168.0.108"  # IP configurada en ALLOWED_HOSTS

$networkAdapter = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ipAddress -ErrorAction SilentlyContinue

if ($networkAdapter) {
    Write-Host "   ✅ IP Local detectada: $ipAddress" -ForegroundColor Green
    Write-Host "   📶 Adaptador: $($networkAdapter.InterfaceAlias)" -ForegroundColor Gray
}
else {
    Write-Host "   ⚠️  IP configurada: $ipAddress (no detectada automáticamente)" -ForegroundColor Yellow
    Write-Host "   Verifica tu IP actual con: ipconfig" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# 4. Verificar Firewall (solo advertencia, no bloqueante)
# ============================================================================
Write-Host "🔥 [4/7] Verificando configuración de Firewall..." -ForegroundColor Cyan

$firewallRule = Get-NetFirewallRule -DisplayName "Django Server5K" -ErrorAction SilentlyContinue
if ($firewallRule) {
    $ruleEnabled = $firewallRule.Enabled
    if ($ruleEnabled -eq "True") {
        Write-Host "   ✅ Regla de firewall 'Django Server5K' está activa" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠️  Regla de firewall existe pero está deshabilitada" -ForegroundColor Yellow
    }
}
else {
    Write-Host "   ⚠️  Regla de firewall no encontrada" -ForegroundColor Yellow
    Write-Host "   Los dispositivos móviles podrían no conectarse" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Para crear la regla (ejecutar PowerShell como Administrador):" -ForegroundColor Yellow
    Write-Host "   New-NetFirewallRule -DisplayName 'Django Server5K' -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow" -ForegroundColor White
}

Write-Host ""

# ============================================================================
# 5. Configurar variables de entorno
# ============================================================================
Write-Host "⚙️  [5/7] Configurando variables de entorno..." -ForegroundColor Cyan
$env:DJANGO_SETTINGS_MODULE = "server.settings"
Write-Host "   ✅ DJANGO_SETTINGS_MODULE configurado" -ForegroundColor Green

# Defaults para Postgres (se pueden overridear antes de ejecutar el script)
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "server5k" }
if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "server5k" }
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = "server5k" }
if (-not $env:POSTGRES_HOST) { $env:POSTGRES_HOST = "127.0.0.1" }
if (-not $env:POSTGRES_PORT) { $env:POSTGRES_PORT = "5433" }  # Puerto 5433 para evitar conflicto con Postgres local
Write-Host "   ✅ Variables POSTGRES_* listas (host=$($env:POSTGRES_HOST):$($env:POSTGRES_PORT))" -ForegroundColor Green

Write-Host ""

# ============================================================================
# 6. Verificar migraciones
# ============================================================================
Write-Host "📦 [6/7] Verificando base de datos..." -ForegroundColor Cyan

# migrate --check devuelve exit code 1 si hay migraciones pendientes
uv run python manage.py migrate --check 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ⚠️  Hay migraciones pendientes, aplicando..." -ForegroundColor Yellow
    uv run python manage.py migrate --noinput
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Migraciones aplicadas correctamente" -ForegroundColor Green
    }
    else {
        Write-Host "   ❌ Error al aplicar migraciones" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "   ✅ Base de datos actualizada" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# 7. Mostrar información de conexión
# ============================================================================
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  📱 Configuración para Apps Móviles" -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  BASE_URL (HTTP/API):" -ForegroundColor White
Write-Host "    http://${ipAddress}:8000" -ForegroundColor Green
Write-Host ""
Write-Host "  WS_URL (WebSocket):" -ForegroundColor White
Write-Host "    ws://${ipAddress}:8000" -ForegroundColor Green
Write-Host ""
Write-Host "  Endpoints disponibles:" -ForegroundColor White
Write-Host "    • Admin:         http://${ipAddress}:8000/admin/" -ForegroundColor Gray
Write-Host "    • API Docs:      http://${ipAddress}:8000/api/docs/" -ForegroundColor Gray
Write-Host "    • API Schema:    http://${ipAddress}:8000/api/schema/" -ForegroundColor Gray
Write-Host "    • WebSocket:     ws://${ipAddress}:8000/ws/juez/{competencia_id}/" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 7. Iniciar servidor Daphne
# ============================================================================
Write-Host "🚀 [7/7] Iniciando servidor Daphne..." -ForegroundColor Cyan
Write-Host "   Binding: 0.0.0.0:8000 (permite conexiones externas)" -ForegroundColor Gray
Write-Host "   Presiona Ctrl+C para detener el servidor" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Iniciar Daphne en todas las interfaces (0.0.0.0) para aceptar conexiones LAN
# Usando múltiples workers para soportar 50+ dispositivos simultáneos
# --proxy-headers: para cuando hay reverse proxy (nginx, etc)
# -v 1: verbosidad baja para mejor rendimiento
uv run daphne -b 0.0.0.0 -p 8000 -v 1 --proxy-headers server.asgi:application

# Si el servidor se detiene
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  ⏹️  Servidor detenido" -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""