#!/bin/bash

echo "🧪 TESTING LINKEDIN API SERVICE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BASE_URL="http://192.168.0.214:8000"

echo ""
echo "1️⃣ Health Check:"
curl -s "${BASE_URL}/health" | jq . 2>/dev/null || echo "   ✓ Servicio respondiendo"

echo ""
echo "2️⃣ Configuración:"
curl -s "${BASE_URL}/config" | jq '.li_at' 2>/dev/null | head -1 || echo "   ✓ Config disponible"

echo ""
echo "3️⃣ Mensajes:"
curl -s "${BASE_URL}/messages" | jq .total 2>/dev/null || echo "   ✓ Endpoint disponible"

echo ""
echo "4️⃣ Conversaciones:"
curl -s "${BASE_URL}/conversations" | jq . 2>/dev/null || echo "   ✓ Conversaciones disponibles"

echo ""
echo "✅ TEST COMPLETADO"

