# Desplegar en Portainer - Guía Paso a Paso

## 🐳 Opción 1: Portainer GUI (Interfaz Visual)

### Requisitos
- Portainer corriendo en http://192.168.0.214:9000
- Usuario y contraseña configurados

### Pasos

#### 1️⃣ Abre Portainer en navegador
```
http://192.168.0.214:9000
```

#### 2️⃣ Login
- Ingresa tu usuario
- Ingresa tu contraseña
- Click "Sign In"

#### 3️⃣ Navega a Stacks
En el menú lateral:
```
Environment → Stacks
```
O directamente:
```
http://192.168.0.214:9000/#/stack
```

#### 4️⃣ Click "Add Stack"
Busca el botón azul "+ Add Stack"

#### 5️⃣ Completa el formulario

**Nombre del Stack:**
```
linkedin-api-gateway
```

**Compose content:**
Copia el contenido de `docker-compose.yml` completo:

```yaml
version: '3.8'

services:
  linkedin-api:
    image: linkedin-api:latest
    container_name: IA_linkedin_api
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

#### 6️⃣ Click "Deploy"
Espera a que aparezca "Stack deployed"

#### 7️⃣ Verifica el estado
- El stack debe aparecer en la lista
- Status: "Active"
- Ver logs: Click en el stack → "Logs"

---

## 🚀 Opción 2: Docker-Compose Directo (RECOMENDADO)

### Por qué es mejor:
✅ Sin autenticación de Portainer
✅ Más rápido
✅ Más control
✅ Fácil de monitorear

### Pasos

#### 1️⃣ En tu terminal, navega al proyecto
```bash
cd /home/node/.openclaw/workspace/linkedin-n8n-gateway
```

#### 2️⃣ Inicia el servicio
```bash
docker-compose up -d
```

#### 3️⃣ Espera 5 segundos
El contenedor se estará iniciando

#### 4️⃣ Verifica que está corriendo
```bash
docker ps | grep linkedin
```

Deberías ver:
```
IA_linkedin_api   linkedin-api:latest   Up X seconds   0.0.0.0:8000->8000/tcp
```

#### 5️⃣ ¡Listo! Accede al servicio
```
http://192.168.0.214:8000/consumer-ui.html
```

---

## 📊 Opción 3: Python Script

### Ejecuta el script deployer
```bash
python portainer-deploy.py
```

El script hará:
1. Conectar a Portainer
2. Verificar autenticación
3. Mostrar instrucciones

---

## 🔍 Verificación Después del Deploy

### Health Check
```bash
curl http://192.168.0.214:8000/health
```

Esperado:
```json
{"status": "ok"}
```

### Ver Logs en Docker
```bash
docker-compose logs -f
```

### Ver Logs en Portainer
1. Portainer → Stacks → linkedin-api-gateway
2. Click en "Logs"

### Detener el Servicio
```bash
docker-compose down
```

---

## 🐛 Troubleshooting

### Error: "Connection refused"
```
❌ Error: No se puede conectar a Portainer
```

**Solución:**
1. Verifica que Portainer está corriendo
2. Prueba acceder a http://192.168.0.214:9000
3. Usa docker-compose en su lugar

### Error: "Unauthorized" (HTTP 401)
```
❌ Portainer requiere autenticación
```

**Soluciones:**
1. Login en Portainer primero
2. O usa docker-compose directamente (recomendado)

### El contenedor no inicia
```
❌ Container exited
```

**Solución:**
1. Ver logs: `docker-compose logs`
2. Verificar puertos disponibles
3. Verificar config/config.json existe

### Puerto 8000 ya está en uso
```
❌ Error: Port 8000 is already allocated
```

**Soluciones:**
1. Detén el servicio anterior:
   ```bash
   docker-compose down
   ```

2. O cambia el puerto en docker-compose.yml:
   ```yaml
   ports:
     - "8080:8000"  # Cambiar 8000 a otro puerto
   ```

---

## ✅ Una vez deployado

### Web UI (RECOMENDADO)
```
http://192.168.0.214:8000/consumer-ui.html
```

### CLI Consumer
```bash
python consume-api.py
```

### Ver Mensajes vía REST
```bash
curl http://192.168.0.214:8000/messages | jq
```

### WebSocket en tiempo real
```javascript
const ws = new WebSocket('ws://192.168.0.214:8000/ws/messages')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
```

---

## 📝 Resumen Rápido

| Método | Comando | Tiempo | Dificultad |
|--------|---------|--------|-----------|
| Portainer GUI | Via navegador | 2 min | Media |
| docker-compose | `docker-compose up -d` | 30 seg | Fácil |
| Python script | `python portainer-deploy.py` | 1 min | Fácil |

**RECOMENDACIÓN:** Usa `docker-compose up -d` - es lo más rápido y directo.
