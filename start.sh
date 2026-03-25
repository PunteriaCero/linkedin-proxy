#!/bin/bash
# Quick start script para LinkedIn-n8n Gateway

echo "🚀 LinkedIn-n8n Gateway | Quick Start"
echo "===================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py no encontrado"
    echo "Asegúrate de estar en el directorio linkedin-n8n-gateway"
    exit 1
fi

# Crear venv si no existe
if [ ! -d "venv" ]; then
    echo "📦 Creando virtual environment..."
    python3 -m venv venv
fi

# Activar venv
echo "✅ Activando venv..."
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

# Instalar dependencias si es necesario
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📥 Instalando dependencias..."
    pip install -q -r requirements.txt
fi

# Ejecutar tests
echo ""
echo "🧪 Ejecutando tests..."
python3 test_gateway.py
test_result=$?

if [ $test_result -eq 0 ]; then
    echo ""
    echo "✅ Todos los tests pasaron!"
    echo ""
    echo "🌐 Iniciando servidor..."
    echo "   Dashboard: http://localhost:8000/admin"
    echo "   Health check: http://localhost:8000/health"
    echo ""
    python3 main.py
else
    echo ""
    echo "❌ Los tests fallaron. Revisa los errores arriba."
    exit 1
fi
