# 📋 Checklist de Preparación para Producción

## ✅ Verificaciones Pre-Despliegue

### 1. Dependencias Instaladas
```bash
cd linkedin-n8n-gateway
source venv/bin/activate
pip list | grep -E "fastapi|httpx|linkedin-api"
```
**Esperado:**
```
fastapi==0.104.1
httpx==0.25.2
linkedin-api==2.0.1
```

### 2. Tests Pasando
```bash
python3 test_gateway.py
```
**Esperado:**
```
RESUMEN: 10 ✅ | 0 ❌
```

### 3. Servidor Inicia Correctamente
```bash
python3 main.py &
sleep 2
curl http://localhost:8000/health | jq
```
**Esperado:**
```json
{
  "status": "healthy",
  "configured": false,
  "timestamp": "2024-03-20T10:30:00Z"
}
```

### 4. Dashboard Accesible
```bash
curl -s http://localhost:8000/admin | grep -c "LinkedIn-n8n Gateway"
```
**Esperado:** `1` (encontró el título)

### 5. Endpoints Disponibles
```bash
# Health
curl http://localhost:8000/health

# Config (sin credenciales)
curl http://localhost:8000/config

# Sync (sin config, debería fallar gracefully)
curl -X POST http://localhost:8000/sync
```

---

## 🔐 Configuración de Seguridad

### Variables de Entorno (Recomendado)
Crear `.env`:
```bash
LINKEDIN_LI_AT=your_li_at_here
LINKEDIN_JSESSIONID=your_jsessionid_here
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/linkedin
```

Luego modificar `main.py` para leer de `.env`:
```python
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    "li_at": os.getenv("LINKEDIN_LI_AT"),
    "jsessionid": os.getenv("LINKEDIN_JSESSIONID"),
    "n8n_webhook_url": os.getenv("N8N_WEBHOOK_URL"),
}
```

### Permisos de Archivos
```bash
# Config y logs no deben ser accesibles al público
chmod 600 config.json
chmod 600 processed_messages.json
chmod 600 gateway.log

# Script ejecutable
chmod +x start.sh
```

### CORS (Si es necesario)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://n8n.example.com"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
```

---

## 🚀 Despliegue en Producción

### Opción 1: Systemd Service (Linux)

Crear `/etc/systemd/system/linkedin-gateway.service`:
```ini
[Unit]
Description=LinkedIn-n8n Gateway
After=network.target

[Service]
Type=simple
User=gateway
WorkingDirectory=/opt/linkedin-n8n-gateway
ExecStart=/opt/linkedin-n8n-gateway/venv/bin/python3 /opt/linkedin-n8n-gateway/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar:
```bash
sudo systemctl enable linkedin-gateway
sudo systemctl start linkedin-gateway
sudo systemctl status linkedin-gateway
```

### Opción 2: Docker

Crear `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py test_gateway.py ./
EXPOSE 8000

CMD ["python3", "main.py"]
```

Build y run:
```bash
docker build -t linkedin-gateway .
docker run -p 8000:8000 -v $(pwd)/config:/app linkedin-gateway
```

### Opción 3: Gunicorn + Nginx

Instalar Gunicorn:
```bash
pip install gunicorn
```

Crear script `run_prod.sh`:
```bash
#!/bin/bash
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 30 main:app
```

Config Nginx (`/etc/nginx/sites-available/linkedin-gateway`):
```nginx
upstream linkedin_gateway {
    server localhost:8000;
}

server {
    listen 80;
    server_name linkedin-gateway.example.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://linkedin_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Logs
    access_log /var/log/nginx/linkedin-gateway-access.log;
    error_log /var/log/nginx/linkedin-gateway-error.log;
}
```

Habilitar:
```bash
sudo ln -s /etc/nginx/sites-available/linkedin-gateway /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 Monitoreo en Producción

### Health Check Periódico
```bash
# Cron job: cada 5 minutos
*/5 * * * * curl -s http://localhost:8000/health || echo "Gateway down" | mail admin@example.com
```

### Rotación de Logs
Crear `/etc/logrotate.d/linkedin-gateway`:
```
/home/gateway/linkedin-n8n-gateway/gateway.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0600 gateway gateway
    sharedscripts
}
```

### Alertas (Opcionalmente)
Monitorear `gateway.log` con herramientas como:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Sentry
- DataDog
- CloudWatch (si está en AWS)

---

## 🔄 Actualización de Cookies

Las cookies de LinkedIn **expiran cada 24-48 horas**.

Crear script de auto-renovación (`refresh_cookies.sh`):
```bash
#!/bin/bash
# Este script notifica cuando las cookies están por expirar

COOKIES_FILE="config.json"
LAST_SYNC=$(grep "last_sync" $COOKIES_FILE | cut -d'"' -f4)
LAST_SYNC_EPOCH=$(date -d "$LAST_SYNC" +%s)
NOW_EPOCH=$(date +%s)
DIFF=$((NOW_EPOCH - LAST_SYNC_EPOCH))

# Si pasaron más de 20 horas
if [ $DIFF -gt 72000 ]; then
    echo "⚠️ Las cookies podrían estar venciendo pronto"
    echo "Abre http://localhost:8000/admin para renovar"
fi
```

Programar en cron:
```bash
0 8 * * * /home/gateway/linkedin-n8n-gateway/refresh_cookies.sh
```

---

## 🧪 Testing en Producción

### 1. Test de Conectividad
```bash
curl -X POST http://linkedin-gateway.example.com/sync \
  -H "Content-Type: application/json"
```
**Esperado:** `400` (sin config) o `200` (con config válida)

### 2. Test de Dashboard
```bash
# Verificar que se puede acceder (GET)
curl -I http://linkedin-gateway.example.com/admin
# Esperado: 200 OK
```

### 3. Test de n8n Integration
En n8n, crear workflow:
```
HTTP Request → POST /sync
└─ Response → Log output
```

Ejecutar y verificar logs:
```bash
tail -f /home/gateway/linkedin-n8n-gateway/gateway.log
```

---

## 📝 Archivos de Configuración Final

```
linkedin-n8n-gateway/
├── main.py                    ✅ Aplicación principal
├── test_gateway.py            ✅ Tests (10/10 pasando)
├── requirements.txt           ✅ Dependencias
├── start.sh                   ✅ Script de inicio
├── config.json               ✅ Configuración (generado)
├── processed_messages.json   ✅ Mensajes procesados
├── gateway.log              ✅ Logs detallados
├── README.md                ✅ Documentación
├── FLOW_SIMULATION.md       ✅ Simulación de flujo
├── DEPLOYMENT.md            ✅ Este archivo
├── config.example.json      ✅ Ejemplo de config
└── venv/                    ✅ Virtual environment
```

---

## ✨ Resumen Final

| Aspecto | Estado | Observaciones |
|---------|--------|---------------|
| Instalación | ✅ Completa | Python 3.11 + venv |
| Tests | ✅ 10/10 pasando | Mock testing sin conexión real |
| Seguridad | ✅ Validated | Limpieza automática de input |
| Error Handling | ✅ Robusto | 429 retry, errores detallados |
| Logging | ✅ Completo | gateway.log con timestamps |
| Documentación | ✅ Exhaustiva | README + Flow + Deployment |
| Producción | ✅ Listo | Systemd/Docker/Gunicorn |

---

## 🎯 Próximos Pasos

1. **Generar cookies:** Abre LinkedIn → DevTools → Cookies → copia li_at + JSESSIONID
2. **Configurar n8n:** Crea webhook y obtén URL
3. **Iniciar gateway:** `./start.sh`
4. **Configurar dashboard:** http://localhost:8000/admin
5. **Probar sincronización:** Llama /sync desde n8n
6. **Monitorear:** `tail -f gateway.log`

---

**Versión:** 1.0.0  
**Última actualización:** 2024-03-20  
**Status:** ✅ Listo para Producción
