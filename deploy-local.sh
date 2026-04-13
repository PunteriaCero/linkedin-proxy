#!/bin/bash

###############################################################################
# 🐳 ALTERNATIVA: DEPLOY LOCAL CON DOCKER-COMPOSE
# Este script ejecuta docker-compose localmente
# Portainer lo verá automáticamente
#
# Uso: ./deploy-local.sh
###############################################################################

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  🐳 DEPLOYING LINKEDIN API WITH DOCKER-COMPOSE        ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "📁 Project: ${PROJECT_DIR}"

echo ""
echo "1️⃣ VERIFICANDO DOCKER"
echo "───────────────────────────────────────────────────────"

if ! command -v docker &> /dev/null; then
    echo "❌ Docker no instalado"
    exit 1
fi

DOCKER_VERSION=$(docker --version | awk '{print $3}')
echo "✅ Docker ${DOCKER_VERSION}"

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ docker-compose no disponible"
    exit 1
fi

echo "✅ docker-compose disponible"

echo ""
echo "2️⃣ VERIFICANDO DOCKERFILE Y DOCKER-COMPOSE"
echo "───────────────────────────────────────────────────────"

if [ ! -f "$PROJECT_DIR/Dockerfile" ]; then
    echo "❌ Dockerfile no encontrado"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "❌ docker-compose.yml no encontrado"
    exit 1
fi

echo "✅ Dockerfile"
echo "✅ docker-compose.yml"

echo ""
echo "3️⃣ CONSTRUYENDO IMAGEN"
echo "───────────────────────────────────────────────────────"

cd "$PROJECT_DIR"

echo "Building linkedin-api:latest..."
docker-compose build

echo "✅ Imagen construida"

echo ""
echo "4️⃣ INICIANDO CONTENEDOR"
echo "───────────────────────────────────────────────────────"

docker-compose up -d

echo "✅ Contenedor iniciado"

echo ""
echo "5️⃣ VERIFICANDO ESTADO"
echo "───────────────────────────────────────────────────────"

sleep 5

CONTAINER_STATUS=$(docker-compose ps | grep "ia-linkedin-api" | awk '{print $NF}')
echo "Estado: ${CONTAINER_STATUS}"

echo ""
echo "6️⃣ VERIFICANDO SERVICIO"
echo "───────────────────────────────────────────────────────"

for i in {1..10}; do
    if curl -s http://192.168.0.214:8000/health > /dev/null 2>&1; then
        echo "✅ SERVICIO RESPONDIENDO!"
        curl -s http://192.168.0.214:8000/health | jq . 2>/dev/null || echo "OK"
        READY="true"
        break
    else
        echo "   Intento $i: Esperando..."
        sleep 2
    fi
done

if [ "$READY" != "true" ]; then
    echo "⏳ Servicio aún iniciando..."
    echo "   Espera 10-15 segundos más"
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ DESPLIEGUE COMPLETADO"
echo "════════════════════════════════════════════════════════"

echo ""
echo "🌐 ACCESO AL SERVICIO:"
echo ""
echo "   Web UI:    http://192.168.0.214:8000/consumer-ui.html"
echo "   Admin:     http://192.168.0.214:8000/admin"
echo "   Health:    curl http://192.168.0.214:8000/health"
echo "   Mensajes:  curl http://192.168.0.214:8000/messages | jq"
echo ""
echo "🐳 CONTENEDOR:"
echo "   Nome: ia-linkedin-api"
echo "   Status: $(docker-compose ps | grep ia-linkedin-api | awk '{print $NF}')"
echo ""
echo "📊 COMANDOS:"
echo ""
echo "   Ver logs:"
echo "     docker-compose logs -f ia-linkedin-api"
echo ""
echo "   Detener:"
echo "     docker-compose stop"
echo ""
echo "   Reiniciar:"
echo "     docker-compose restart"
echo ""
echo "   Eliminar:"
echo "     docker-compose down"
echo ""
echo "🐳 PORTAINER VERÁ AUTOMÁTICAMENTE:"
echo "   http://192.168.0.214:9000/#!/docker/containers"
echo ""
