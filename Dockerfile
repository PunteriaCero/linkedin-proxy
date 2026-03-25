# Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias en wheels
RUN pip install --user --no-cache-dir -r requirements.txt


# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copiar usuario de pip del builder
COPY --from=builder /root/.local /root/.local

# Agregar local bin al PATH
ENV PATH=/root/.local/bin:$PATH

# Copiar aplicación
COPY main.py test_gateway.py ./
COPY config.example.json .env.example ./

# Crear directorios para datos persistentes
RUN mkdir -p /app/logs /app/data /app/config

# ===== VOLUMES PARA PERSISTENCIA =====
# Directorio de logs - accesible desde afuera
VOLUME ["/app/logs"]

# Directorio de configuración y datos
VOLUME ["/app/data"]

# Archivos individuales de configuración (si se montan directamente)
VOLUME ["/app/config"]

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Ejecutar aplicación
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
