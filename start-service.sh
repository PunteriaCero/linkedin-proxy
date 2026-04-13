#!/bin/bash

echo "🚀 INICIANDO LINKEDIN API SERVICE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verificar que docker-compose está disponible
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose no encontrado"
    echo "   Instala Docker Desktop o docker-compose"
    exit 1
fi

# Mostrar configuración
echo ""
echo "📋 CONFIGURACIÓN:"
echo "  Servicio: LinkedIn API"
echo "  Puerto: 8000"
echo "  Contenedor: IA_linkedin_api"
echo "  Estado: Iniciando..."

echo ""
echo "🐳 Levantando contenedor..."

# Usar docker-compose para desplegar
docker-compose up -d

# Esperar a que el servicio esté listo
echo ""
echo "⏳ Esperando a que el servicio esté listo..."
sleep 5

# Verificar salud del servicio
echo ""
echo "🔍 Verificando salud del servicio..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Servicio está corriendo!"
        break
    else
        echo "   Intento $i/10... esperando..."
        sleep 2
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ LINKEDIN API INICIADO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📍 ENDPOINTS DISPONIBLES:"
echo ""
echo "  🔌 REST API"
echo "     GET  http://192.168.0.214:8000/health     - Health check"
echo "     GET  http://192.168.0.214:8000/admin      - Admin panel"
echo "     GET  http://192.168.0.214:8000/config     - Configuración"
echo "     GET  http://192.168.0.214:8000/messages   - Mensajes"
echo ""
echo "  📡 WebSocket (NUEVO)"
echo "     ws://192.168.0.214:8000/ws/messages       - Stream en tiempo real"
echo "     GET  http://192.168.0.214:8000/conversations     - Lista conversaciones"
echo "     GET  http://192.168.0.214:8000/monitor/stats     - Estadísticas"
echo ""
echo "📋 COMANDOS ÚTILES:"
echo ""
echo "  Ver logs en vivo:"
echo "     docker-compose logs -f"
echo ""
echo "  Detener servicio:"
echo "     docker-compose down"
echo ""
echo "  Ver estado del contenedor:"
echo "     docker ps -a | grep IA_linkedin_api"
echo ""
echo "  Ver credenciales configuradas:"
echo "     cat config/config.json"
echo ""

