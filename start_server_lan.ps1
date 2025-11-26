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
Write-Host "📡 [1/6] Verificando Redis en Docker..." -ForegroundColor Cyan

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
# 2. Obtener y mostrar IP Local
# ============================================================================
Write-Host "🌐 [2/6] Verificando configuración de red..." -ForegroundColor Cyan

$ipAddress = "192.168.0.190"  # IP configurada en ALLOWED_HOSTS
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
# 3. Verificar Firewall (solo advertencia, no bloqueante)
# ============================================================================
Write-Host "🔥 [3/6] Verificando configuración de Firewall..." -ForegroundColor Cyan

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
# 4. Configurar variables de entorno
# ============================================================================
Write-Host "⚙️  [4/6] Configurando variables de entorno..." -ForegroundColor Cyan
$env:DJANGO_SETTINGS_MODULE = "server.settings"
Write-Host "   ✅ DJANGO_SETTINGS_MODULE configurado" -ForegroundColor Green

Write-Host ""

# ============================================================================
# 5. Verificar migraciones
# ============================================================================
Write-Host "📦 [5/6] Verificando base de datos..." -ForegroundColor Cyan

$migrationCheck = uv run python manage.py showmigrations --plan 2>&1 | Select-String "\[ \]"
if ($migrationCheck) {
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
# 6. Mostrar información de conexión
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
Write-Host "🚀 [6/6] Iniciando servidor Daphne..." -ForegroundColor Cyan
Write-Host "   Binding: 0.0.0.0:8000 (permite conexiones externas)" -ForegroundColor Gray
Write-Host "   Presiona Ctrl+C para detener el servidor" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Iniciar Daphne en todas las interfaces (0.0.0.0) para aceptar conexiones LAN
uv run daphne -b 0.0.0.0 -p 8000 server.asgi:application

# Si el servidor se detiene
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  ⏹️  Servidor detenido" -ForegroundColor Yellow
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
