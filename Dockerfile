FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente REQUERIDO
COPY main.py .
COPY connection_manager.py .
COPY websocket_integration.py .
COPY voyager_helper.py .

# Crear directorios necesarios
RUN mkdir -p config data logs

# Exponer puerto
EXPOSE 8000

# Healthcheck (verifica que el puerto está escuchando)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
