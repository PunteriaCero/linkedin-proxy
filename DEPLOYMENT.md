# 🚀 DEPLOYMENT: LinkedIn API Service

**Fecha:** 13 Apr 2026 - 03:30 UTC  
**Status:** ✅ Listo para deploy  
**Versión:** 1.0.0  

---

## Opción 1: Docker Compose (RECOMENDADO)

### Prerrequisitos
- Docker >= 20.10
- Docker Compose >= 1.29

### Instrucciones

```bash
# 1. Navegar al directorio
cd /home/node/.openclaw/workspace/linkedin-n8n-gateway

# 2. Construir y levantar el servicio
docker-compose up -d

# 3. Verificar que está corriendo
docker ps | grep IA_linkedin_api

# 4. Ver logs
docker-compose logs -f

# 5. Detener (cuando necesites)
docker-compose down
```

### Verificar que funciona

```bash
# Health check
curl http://192.168.0.214:8000/health

# Config
curl http://192.168.0.214:8000/config

# Admin panel (en navegador)
http://192.168.0.214:8000/admin
```

---

## Opción 2: Docker Build Manual

```bash
# 1. Construir imagen
docker build -t linkedin-api:latest .

# 2. Ejecutar contenedor
docker run -d \
  --name IA_linkedin_api \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e PYTHONUNBUFFERED=1 \
  linkedin-api:latest

# 3. Verificar logs
docker logs -f IA_linkedin_api

# 4. Detener
docker stop IA_linkedin_api
docker rm IA_linkedin_api
```

---

## Opción 3: Python + Uvicorn (Desarrollo Local)

### Prerrequisitos
- Python 3.11+
- pip

### Instalación de dependencias

```bash
# Instalar dependencias
pip install -r requirements.txt

# O instalar manualmente
pip install fastapi==0.104.1
pip install uvicorn==0.24.0
pip install websockets==12.0
pip install linkedin-api==2.0.1
pip install httpx==0.25.2
pip install requests==2.31.0
pip install pydantic==2.5.0
```

### Iniciar servicio

```bash
# Iniciar en foreground (desarrollo)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# O iniciar en background
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
```

---

## Opción 4: Portainer (Docker Management)

### Instrucciones

1. Abrir Portainer
   ```
   http://192.168.0.214:9000
   ```

2. Ir a **Stacks** → **+ Add Stack**

3. Copiar contenido de `docker-compose.yml`:
   ```yaml
   version: '3.8'

   services:
     linkedin-api:
       build:
         context: .
         dockerfile: Dockerfile
       container_name: IA_linkedin_api
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
   ```

4. Hacer Deploy

5. Verificar que el contenedor está **Running**

---

## Verificación Post-Deploy

### 1. Health Check
```bash
curl -i http://192.168.0.214:8000/health
```
**Esperado:** HTTP 200

### 2. Configuración cargada
```bash
curl http://192.168.0.214:8000/config | jq '.li_at'
```
**Esperado:** Token de LinkedIn (primeros 20 caracteres)

### 3. Admin Panel
```
http://192.168.0.214:8000/admin
```
**Esperado:** Panel web funcional

### 4. WebSocket conectado
```bash
# Test simple con curl
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://192.168.0.214:8000/ws/messages
```

### 5. Conversaciones
```bash
curl http://192.168.0.214:8000/conversations | jq .
```

---

## Credenciales Configuradas

Las credenciales están en `config/config.json`:

```json
{
  "li_at": "AQEDAWYpp_UFjt1...",          // Session token
  "jsessionid": "ajax:0224706131...",     // Session ID
  "bcookie": "v=2&d63144af-95...",        // Browser cookie
  "lidc": "b=TB05:s=T:r=T:a=T:p...",      // Data center
  "aam_uuid": "74259222753135...",        // Tracking
  "n8n_webhook_url": "",                  // (Opcional)
  "last_sync": "2026-03-25T12:29:18..."  // Timestamp
}
```

**⚠️ IMPORTANTE:** No compartir estas credenciales. Son personales y permiten acceso a tu cuenta LinkedIn.

---

## Endpoints Disponibles

### REST API (12)

```
GET      /                   - Home page
GET      /admin              - Admin panel
POST     /admin              - Update config
POST     /parse-curl         - Parser de curl
POST     /sync               - Sincronizar con n8n
POST     /reply              - Enviar respuesta
GET      /health             - Health check
GET      /config             - Ver configuración
GET      /logs               - Logs HTML
GET      /logs/json          - Logs JSON
POST     /validate-cookies   - Validar credenciales
GET      /messages           - Obtener mensajes
```

### WebSocket (5 NUEVOS)

```
GET      /ws/messages        - Stream tiempo real
GET      /conversations      - Lista conversaciones
GET      /conversations/{id}/messages - Historial
GET      /monitor/stats      - Estadísticas
POST     /monitor/restart    - Reiniciar monitor
```

---

## Performance Esperado

| Métrica | Valor |
|---------|-------|
| Latencia WebSocket | <2s |
| Cache TTL | 5 minutos |
| Polling | 30 segundos |
| Conexiones | 3+ simultáneas |
| Memoria | ~50 MB |
| CPU (idle) | 5-10% |
| Uptime | 99.5% |

---

## Troubleshooting

### Puerto 8000 ya en uso

```bash
# Encontrar proceso usando puerto 8000
lsof -i :8000

# Matar proceso (si es necesario)
kill -9 <PID>

# O usar puerto diferente en docker-compose
ports:
  - "8001:8000"  # Local 8001 → Container 8000
```

### Credenciales inválidas

```bash
# Verificar que config.json está correcto
cat config/config.json

# Validar credenciales
curl -X POST http://192.168.0.214:8000/validate-cookies \
  -H "Content-Type: application/json" \
  -d '{
    "li_at": "...",
    "jsessionid": "...",
    "bcookie": "...",
    "lidc": "..."
  }'
```

### Ver logs

```bash
# Docker
docker logs IA_linkedin_api -f

# O archivo
tail -f logs/api.log

# O JSON
curl http://192.168.0.214:8000/logs/json
```

---

## Detener y Limpiar

```bash
# Detener contenedor
docker-compose down

# Remover datos persistentes (CUIDADO)
docker-compose down -v

# O si usaste docker run
docker stop IA_linkedin_api
docker rm IA_linkedin_api
```

---

## Próximos Pasos

1. ✅ Levantar servicio
2. ✅ Verificar que está corriendo
3. ⏳ Conectar cliente WebSocket
4. ⏳ Probar streaming en tiempo real
5. ⏳ Validar performance
6. ⏳ Integrar con N8N

---

## Links Útiles

- **GitHub:** https://github.com/PunteriaCero/linkedin-proxy
- **Admin Panel:** http://192.168.0.214:8000/admin
- **Portainer:** http://192.168.0.214:9000
- **N8N:** (si está configurado)

---

**Documento generado:** 13 Apr 2026 - 03:30 UTC  
**Status:** ✅ LISTO PARA DEPLOYMENT
