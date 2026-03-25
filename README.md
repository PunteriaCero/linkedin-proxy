# LinkedIn-n8n Gateway 🔗

Microservicio en FastAPI que sincroniza mensajes de LinkedIn hacia n8n usando **cookies de sesión** (sin email/password).

## 📋 Características

✅ **Dashboard Admin** (GET /admin) - Configurar cookies y webhook URL  
✅ **Validación Automática** - Prueba de conexión inmediata al guardar  
✅ **Sincronización Inteligente** (/sync) - Evita duplicados con processed_messages.json  
✅ **Respuestas** (/reply) - Envía mensajes desde n8n hacia LinkedIn  
✅ **Manejo de Errores** - Rate limiting (429), detección de cookies expiradas  
✅ **Logging Detallado** - Auditoría completa en gateway.log  
✅ **Mock Testing** - test_gateway.py sin necesidad de conexión real  

---

## 🚀 Instalación

### 1. Instalar dependencias

```bash
cd linkedin-n8n-gateway
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ejecutar tests

```bash
python3 test_gateway.py
```

Deberías ver:
```
RESUMEN: 10 ✅ | 0 ❌
```

### 3. Iniciar el servicio

```bash
python3 main.py
```

El gateway inicia en **http://localhost:8000**

---

## 🔐 Configuración (Dashboard)

Abre **http://localhost:8000/admin** y completa:

### 1️⃣ LinkedIn Cookie (li_at)
- Abre LinkedIn en tu navegador
- DevTools → Application → Cookies → busca `li_at`
- Copia el valor completo

### 2️⃣ JSESSIONID Cookie
- En el mismo lugar, busca `JSESSIONID`
- Copia el valor (no importa si tiene comillas)
- El gateway lo limpia automáticamente

### 3️⃣ n8n Webhook URL
- Crea un webhook en n8n
- Copia la URL completa (ej: `https://n8n.example.com/webhook/linkedin`)

### Guardar & Validar
- Al hacer click en **Guardar**, el gateway:
  1. Limpia los datos (quita comillas, espacios)
  2. Llama a `get_profile()` de LinkedIn
  3. Si falla, muestra el error exacto
  4. Si es válido, lo guarda en `config.json`

---

## 📡 Endpoints

### GET /admin
Dashboard para configuración (form HTML)

### POST /admin
Guarda la configuración con validación automática

### POST /sync
Sincroniza mensajes nuevos de LinkedIn hacia n8n

**Response:**
```json
{
  "status": "success",
  "messages_synced": 5,
  "n8n_response": {...}
}
```

### POST /reply
Envía una respuesta a una conversación

**Body:**
```json
{
  "conversation_id": "conv_12345",
  "text": "Tu respuesta aquí"
}
```

**Response:**
```json
{
  "status": "sent",
  "conversation_id": "conv_12345",
  "message_id": "msg_response_001",
  "timestamp": "2024-03-20T10:30:00Z"
}
```

### GET /health
Health check

**Response:**
```json
{
  "status": "healthy",
  "configured": true,
  "timestamp": "2024-03-20T10:30:00Z"
}
```

### GET /config
Estado de la configuración (sin exponer secretos)

---

## 📊 Flujo de Sincronización

```
1. n8n → POST /sync
2. Gateway carga config.json
3. Conecta a LinkedIn con cookies
4. Obtiene conversaciones + mensajes
5. Compara con processed_messages.json
6. Identifica mensajes NUEVOS
7. Transforma a formato n8n
8. Envía POST al n8n webhook
9. n8n responde (200 OK)
10. Gateway actualiza processed_messages.json
11. Response con resumen
```

---

## ⚙️ Manejo de Errores

### Cookie Expirada (401)
```
❌ Error de validación: Cookie expirada o inválida (401)
```
→ Re-genera cookies en LinkedIn

### Rate Limit (429)
```
⚠️ Rate limit (429) en sync. Reintentando en 1s...
```
→ El gateway reintenta automáticamente con backoff exponencial (1s → 2s → 4s)

### JSESSIONID Inválido
```
❌ Error de validación: Estructura de JSESSIONID incorrecta
```
→ Verifica que copiaste la cookie completa

### n8n No Accesible
```
❌ Error en sincronización: n8n no accesible
```
→ Verifica que el webhook URL es correcto y accesible

---

## 📝 Archivos Generados

- **config.json** - Configuración (li_at, jsessionid, webhook_url)
- **processed_messages.json** - IDs de mensajes ya procesados
- **gateway.log** - Log detallado de todas las operaciones

---

## 🧪 Testing

### Ejecutar suite completa

```bash
python3 test_gateway.py
```

Tests incluidos:
1. ✅ Persistencia de config
2. ✅ Limpieza de JSESSIONID
3. ✅ Parseo LinkedIn → n8n
4. ✅ Prevención de duplicados
5. ✅ Reintentos exponenciales (429)
6. ✅ Mensajes de error detallados
7. ✅ Flujo completo
8. ✅ Estructura de payload
9. ✅ Endpoint /reply
10. ✅ Logging chain

---

## 🔍 Debugging

### Ver logs en tiempo real

```bash
tail -f gateway.log
```

### Ejemplo de log completo

```
2024-03-20T10:30:00 - INFO - === INICIANDO SINCRONIZACIÓN ===
2024-03-20T10:30:00 - INFO - Conectando a LinkedIn...
2024-03-20T10:30:01 - INFO - Obteniendo conversaciones...
2024-03-20T10:30:02 - INFO - Nuevo mensaje encontrado: msg_001
2024-03-20T10:30:02 - INFO - Enviando 5 mensajes a n8n...
2024-03-20T10:30:03 - INFO - Respuesta de n8n: 200
2024-03-20T10:30:03 - INFO - ✓ Sincronización completada exitosamente
```

---

## 🚨 Producción

Para usar en producción con Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

Con Nginx (proxy reverso recomendado):
```nginx
server {
    listen 80;
    server_name linkedin-gateway.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📚 Estructura del Proyecto

```
linkedin-n8n-gateway/
├── main.py                    # Aplicación principal (FastAPI)
├── test_gateway.py            # Suite de tests (mock)
├── requirements.txt           # Dependencias
├── config.json               # Configuración (generado)
├── processed_messages.json   # IDs procesados (generado)
├── gateway.log              # Logs (generado)
└── README.md                # Este archivo
```

---

## 🎯 Próximos Pasos

1. Generar cookies de LinkedIn
2. Configurar webhook en n8n
3. Abrir http://localhost:8000/admin
4. Guardar & validar
5. Probar /sync desde n8n

---

## 📝 Notas

- Las cookies **expiran cada ~24 horas** - tendrás que regenerarlas
- El gateway **no almacena contraseñas**, solo cookies
- Los mensajes se marcan como "procesados" para evitar duplicados
- Todos los errores se logguean detalladamente en `gateway.log`

---

**Versión:** 1.0.0  
**Autor:** Tito (OpenClaw)  
**Última actualización:** 2024-03-20
