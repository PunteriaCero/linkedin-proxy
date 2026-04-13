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

# Copiar código
COPY main.py .
COPY connection_manager.py .
COPY websocket_integration.py .
COPY linkedin_login.py .
COPY voyager_helper.py .
COPY config/ ./config/
COPY data/ ./data/ 2>/dev/null || true
COPY logs/ ./logs/ 2>/dev/null || true

# Crear directorios si no existen
RUN mkdir -p config data logs

# Exponer puerto
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

