#!/bin/bash

# Deploy LinkedIn API container using docker-compose
# Ejecutar desde: /home/node/.openclaw/workspace/linkedin-n8n-gateway/

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🚀 LINKEDIN API - CONTAINER DEPLOYMENT                       ║"
echo "║                                                                ║"
echo "║  Este script despliega el contenedor ia-linkedin-api          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

echo "📍 Working directory: $(pwd)"
echo ""

# Step 1: Stop and remove any existing container
echo "1️⃣ Deteniendo contenedor anterior (si existe)..."
echo ""

docker-compose down -v 2>/dev/null || docker compose down -v 2>/dev/null || true

echo ""
echo "2️⃣ Pulleando imagen desde DockerHub..."
echo "   Imagen: punteria/linkedin-api:latest"
echo ""

docker pull punteria/linkedin-api:latest || {
  echo "⚠️ Error pulleando imagen de DockerHub"
  echo "   Alternativa: Hacer build local desde Dockerfile"
  echo ""
}

echo ""
echo "3️⃣ Iniciando contenedor..."
echo ""

# Try docker-compose first, then docker compose
if command -v docker-compose &> /dev/null; then
  docker-compose up -d
else
  docker compose up -d
fi

echo ""
echo "4️⃣ Esperando que el contenedor inicie..."
sleep 3

echo ""
echo "5️⃣ Estado del contenedor..."
echo ""

if command -v docker-compose &> /dev/null; then
  docker-compose ps
else
  docker compose ps
fi

echo ""
echo "6️⃣ Últimos logs..."
echo ""

if command -v docker-compose &> /dev/null; then
  docker-compose logs --tail=15
else
  docker compose logs --tail=15
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETADO"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Container Details:"
echo "  • Nombre: ia-linkedin-api"
echo "  • Imagen: punteria/linkedin-api:latest"
echo "  • Puerto: 8000"
echo "  • Status: check arriba ☝️"
echo ""
echo "🌐 Acceso al Servicio:"
echo "  • Web UI: http://192.168.0.214:8000/consumer-ui.html"
echo "  • Health: http://192.168.0.214:8000/health"
echo "  • API: http://192.168.0.214:8000"
echo ""
echo "🛠️ Comandos Útiles:"
echo ""
echo "  # Ver logs en tiempo real"
echo "  docker-compose logs -f"
echo ""
echo "  # Detener contenedor"
echo "  docker-compose down"
echo ""
echo "  # Ejecutar comando dentro del contenedor"
echo "  docker-compose exec linkedin-api python -c 'print(1+1)'"
echo ""
echo "  # Ver estadísticas de recursos"
echo "  docker stats ia-linkedin-api"
echo ""
echo "════════════════════════════════════════════════════════════════"
