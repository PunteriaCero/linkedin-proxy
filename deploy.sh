#!/bin/bash
# Deploy LinkedIn API Service
# Ejecutar en tu máquina (no en OpenClaw)

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🚀 DESPLEGANDO LINKEDIN API SERVICE                          ║"
echo "║                                                                ║"
echo "║  Fecha: $(date)                                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/home/node/.openclaw/workspace/linkedin-n8n-gateway"

echo "📍 VERIFICANDO ENTORNO"
echo "========================================================================"

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml no encontrado"
    echo ""
    echo "Cambia al directorio del proyecto:"
    echo "  cd /home/node/.openclaw/workspace/linkedin-n8n-gateway"
    echo ""
    exit 1
fi

echo "✅ docker-compose.yml encontrado"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado"
    echo "   Instálalo desde: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker está instalado: $(docker --version)"

# Verificar docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose no está instalado"
    echo "   Intenta: docker compose up -d (Docker v20.10+)"
    
    # Intentar con nueva sintaxis de docker
    if docker compose version &> /dev/null; then
        echo ""
        echo "✅ Encontré 'docker compose' (nueva sintaxis)"
        DOCKER_CMD="docker compose"
    else
        echo "   O instala: pip install docker-compose"
        exit 1
    fi
else
    DOCKER_CMD="docker-compose"
    echo "✅ docker-compose está disponible"
fi

echo ""
echo "🔧 DETENIENDO CONTENEDORES EXISTENTES (si los hay)"
echo "========================================================================"

$DOCKER_CMD down 2>/dev/null || echo "   (no hay contenedores previos)"

echo ""
echo "🚀 INICIANDO SERVICIO CON $DOCKER_CMD"
echo "========================================================================"
echo ""

$DOCKER_CMD up -d

echo ""
echo "⏳ ESPERANDO A QUE EL SERVICIO ESTÉ LISTO..."
echo "========================================================================"

sleep 5

# Verificar que el contenedor está corriendo
if docker ps | grep -q "IA_linkedin_api"; then
    echo "✅ Contenedor IA_linkedin_api está corriendo"
    echo ""
    docker ps | grep linkedin
else
    echo "❌ El contenedor no está corriendo"
    echo ""
    echo "Verificando logs:"
    $DOCKER_CMD logs
    exit 1
fi

echo ""
echo "🏥 VERIFICANDO HEALTH CHECK"
echo "========================================================================"

# Intentar health check
for i in {1..10}; do
    if curl -s http://192.168.0.214:8000/health > /dev/null 2>&1; then
        echo "✅ Health check exitoso"
        break
    else
        echo "   Intento $i/10... esperando"
        sleep 1
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "✅ ¡SERVICIO DESPLEGADO EXITOSAMENTE!"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

echo "📍 ACCESO INMEDIATO:"
echo ""
echo "🌐 Web UI (RECOMENDADO - Interfaz visual):"
echo "   http://192.168.0.214:8000/consumer-ui.html"
echo ""
echo "📊 Admin Panel:"
echo "   http://192.168.0.214:8000/admin"
echo ""
echo "📬 REST API - Últimos mensajes:"
echo "   curl http://192.168.0.214:8000/messages | jq"
echo ""
echo "👥 REST API - Conversaciones:"
echo "   curl http://192.168.0.214:8000/conversations | jq"
echo ""
echo "📈 REST API - Estadísticas:"
echo "   curl http://192.168.0.214:8000/monitor/stats | jq"
echo ""
echo "📡 WebSocket (Tiempo real):"
echo "   ws://192.168.0.214:8000/ws/messages"
echo ""
echo "🔧 CLI Consumer:"
echo "   python consume-api.py"
echo ""

echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "🎯 SIGUIENTES PASOS:"
echo "   1. Abre en navegador: http://192.168.0.214:8000/consumer-ui.html"
echo "   2. Haz click en 'Verificar Salud' para probar"
echo "   3. Haz click en 'Obtener Mensajes' para ver los chats"
echo "   4. Explora conversaciones"
echo "   5. ¡Disfruta!"
echo ""

echo "🛑 PARA DETENER EL SERVICIO:"
echo "   $DOCKER_CMD down"
echo ""

echo "📋 PARA VER LOGS:"
echo "   $DOCKER_CMD logs -f"
echo ""
