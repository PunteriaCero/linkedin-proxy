# 🐳 Deployment via Portainer UI - Step by Step

## Opción 1: Usando Stacks (Recomendado)

### Paso 1: Acceder a Portainer
```
URL: http://192.168.0.214:9000
```

### Paso 2: Ir a Stacks
```
Left Menu → Stacks → Add Stack
```

### Paso 3: Crear Stack con docker-compose

**Nombre del Stack:**
```
ia-linkedin-api
```

**Paste el siguiente docker-compose.yml:**

```yaml
version: '3.8'

services:
  linkedin-api:
    image: punteria/linkedin-api:latest
    container_name: ia-linkedin-api
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; socket.create_connection(('localhost', 8000), timeout=2)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M

volumes:
  config:
  data:
  logs:

networks:
  default:
    driver: bridge
```

### Paso 4: Seleccionar Endpoint
```
Endpoint: local
```

### Paso 5: Deploy
```
Click: Deploy the stack
```

---

## Opción 2: Usando Containers (Manual)

### Paso 1: Acceder a Portainer
```
URL: http://192.168.0.214:9000
```

### Paso 2: Ir a Images
```
Left Menu → Images → Pull Image
```

### Paso 3: Pull image desde DockerHub
```
Image name: punteria/linkedin-api:latest
Click: Pull the image
```

### Paso 4: Crear Container
```
Left Menu → Containers → Create container
```

### Configurar:
```
Name: ia-linkedin-api

Image: punteria/linkedin-api:latest

Port mapping:
  Container: 8000
  Host: 8000

Volumes:
  /app/config
  /app/data
  /app/logs

Environment variables:
  PYTHONUNBUFFERED=1
  LOG_LEVEL=INFO

Restart policy: Unless stopped

Resource limits:
  CPU: 2
  Memory: 1GB
```

### Paso 5: Deploy
```
Click: Create the container
```

---

## Monitoreo

### En Portainer:
```
Containers → ia-linkedin-api
  • Ver estado
  • Ver logs
  • Inspeccionar recursos
```

### Health Check:
```
curl http://192.168.0.214:8000/health
```

### Acceso al Servicio:
```
Web: http://192.168.0.214:8000/consumer-ui.html
API: http://192.168.0.214:8000
```

---

## Troubleshooting

### Si el container no inicia:
1. Verifica los logs en Portainer
2. Confirma que la imagen existe en DockerHub
3. Verifica el puerto 8000 no está en uso

### Si la imagen no existe:
1. Verifica que el pipeline de Docker build completó exitosamente
2. Revisa DockerHub: https://hub.docker.com/r/punteria/linkedin-api
3. Rebuild manualmente si es necesario

### Si hay problemas de conexión:
1. Verifica que el container está en estado "Running"
2. Prueba: `docker logs ia-linkedin-api`
3. Verifica healthcheck: `curl http://192.168.0.214:8000/health`

---

## Resultado Esperado

```
✅ Container: ia-linkedin-api (Running)
✅ Puerto: 8000 (accessible)
✅ Health: OK (socket connection passes)
✅ Web UI: http://192.168.0.214:8000/consumer-ui.html
```

---

*Guía creada: Apr 13, 2026 - 12:00 UTC*
*Status: Production Ready*
