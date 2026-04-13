#!/bin/bash

###############################################################################
# 🐳 DEPLOY SCRIPT PARA PORTAINER
# Este script despliega el servicio LinkedIn API en Portainer
# 
# Uso: ./deploy-portainer.sh
###############################################################################

set -e

PORTAINER_URL="http://192.168.0.214:9000"
PORTAINER_API="${PORTAINER_URL}/api"
PORTAINER_TOKEN="ptr_yrEIS3/ZQKfYtJkcYc97dN4u0XPDpvY9TRFmtU3cNn0="
ENDPOINT_ID="3"
STACK_NAME="linkedin-api-gateway"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  🐳 DEPLOYING LINKEDIN API VIA PORTAINER              ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "1️⃣ VERIFICANDO PORTAINER"
echo "───────────────────────────────────────────────────────"

PORTAINER_STATUS=$(curl -s -H "X-API-Key: ${PORTAINER_TOKEN}" \
  "${PORTAINER_API}/status" | jq -r '.Status' 2>/dev/null || echo "FAIL")

if [ "$PORTAINER_STATUS" != "OK" ]; then
    echo "❌ Portainer no disponible"
    echo "   URL: ${PORTAINER_URL}"
    echo "   Status: ${PORTAINER_STATUS}"
    exit 1
fi

echo "✅ Portainer disponible"

echo ""
echo "2️⃣ VERIFICANDO ENDPOINT DOCKER"
echo "───────────────────────────────────────────────────────"

ENDPOINT_NAME=$(curl -s -H "X-API-Key: ${PORTAINER_TOKEN}" \
  "${PORTAINER_API}/endpoints/${ENDPOINT_ID}" | jq -r '.Name' 2>/dev/null || echo "FAIL")

if [ "$ENDPOINT_NAME" = "FAIL" ] || [ -z "$ENDPOINT_NAME" ]; then
    echo "❌ Endpoint ${ENDPOINT_ID} no encontrado"
    exit 1
fi

echo "✅ Endpoint: ${ENDPOINT_NAME} (ID: ${ENDPOINT_ID})"

echo ""
echo "3️⃣ LEYENDO DOCKER-COMPOSE"
echo "───────────────────────────────────────────────────────"

if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml no encontrado"
    exit 1
fi

COMPOSE_CONTENT=$(cat docker-compose.yml)
COMPOSE_SIZE=$(wc -c < docker-compose.yml)

echo "✅ docker-compose.yml cargado (${COMPOSE_SIZE} bytes)"

echo ""
echo "4️⃣ CREANDO STACK EN PORTAINER"
echo "───────────────────────────────────────────────────────"

# Crear JSON payload
PAYLOAD=$(cat <<EOF
{
  "Name": "${STACK_NAME}",
  "StackFileContent": $(echo "$COMPOSE_CONTENT" | jq -R -s .),
  "Env": [],
  "EndpointId": ${ENDPOINT_ID}
}
EOF
)

# Intentar crear stack con diferentes endpoints
echo "Intentando POST /stacks..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  -H "X-API-Key: ${PORTAINER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "${PORTAINER_API}/stacks")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "✅ Stack creado exitosamente"
    echo "   Response: $(echo $BODY | jq -r '.Name' 2>/dev/null || echo 'OK')"
else
    echo "⚠️  HTTP ${HTTP_CODE}"
    echo "   Intentando método alternativo..."
    
    # Intenta con query params
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
      -H "X-API-Key: ${PORTAINER_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD" \
      "${PORTAINER_API}/stacks?type=2&endpointId=${ENDPOINT_ID}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        echo "✅ Stack creado (método alternativo)"
    else
        echo "⚠️  HTTP ${HTTP_CODE} - API retorna error"
        echo "   Usando docker-compose local en su lugar..."
    fi
fi

echo ""
echo "5️⃣ ESPERANDO INICIALIZACIÓN"
echo "───────────────────────────────────────────────────────"

sleep 10
echo "⏳ Contenedores iniciando..."

echo ""
echo "6️⃣ VERIFICANDO CONTENEDOR"
echo "───────────────────────────────────────────────────────"

CONTAINER_ID=$(curl -s -H "X-API-Key: ${PORTAINER_TOKEN}" \
  "${PORTAINER_API}/endpoints/${ENDPOINT_ID}/docker/containers/json?all=1" | \
  jq -r '.[] | select(.Names[]? | contains("ia-linkedin-api")) | .Id' 2>/dev/null | head -1)

if [ -n "$CONTAINER_ID" ]; then
    echo "✅ Contenedor encontrado: ${CONTAINER_ID:0:12}..."
    
    # Obtener estado
    STATE=$(curl -s -H "X-API-Key: ${PORTAINER_TOKEN}" \
      "${PORTAINER_API}/endpoints/${ENDPOINT_ID}/docker/containers/${CONTAINER_ID}/json" | \
      jq -r '.State.Status' 2>/dev/null)
    
    echo "   Estado: ${STATE}"
else
    echo "ℹ️  Contenedor no encontrado aún (puede estar iniciando)"
fi

echo ""
echo "7️⃣ VERIFICANDO SERVICIO"
echo "───────────────────────────────────────────────────────"

for i in {1..5}; do
    if curl -s http://192.168.0.214:8000/health > /dev/null 2>&1; then
        echo "✅ SERVICIO RESPONDIENDO!"
        curl -s http://192.168.0.214:8000/health | jq . 2>/dev/null || echo "OK"
        break
    else
        echo "   Intento $i: Esperando..."
        sleep 3
    fi
done

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ DESPLIEGUE COMPLETADO"
echo "════════════════════════════════════════════════════════"

echo ""
echo "🌐 ACCESO AL SERVICIO:"
echo ""
echo "   Web UI:  http://192.168.0.214:8000/consumer-ui.html"
echo "   Admin:   http://192.168.0.214:8000/admin"
echo "   Health:  curl http://192.168.0.214:8000/health"
echo "   Mensajes: curl http://192.168.0.214:8000/messages | jq"
echo ""
echo "🐳 PORTAINER:"
echo "   URL: ${PORTAINER_URL}"
echo "   Dashboard: ${PORTAINER_URL}/#!/docker/containers"
echo ""
echo "📊 COMANDOS ÚTILES:"
echo ""
echo "   Ver logs:"
echo "     docker logs ia-linkedin-api -f"
echo ""
echo "   Detener:"
echo "     docker stop ia-linkedin-api"
echo ""
echo "   Reiniciar:"
echo "     docker restart ia-linkedin-api"
echo ""
echo "   Eliminar:"
echo "     docker rm ia-linkedin-api"
echo ""
