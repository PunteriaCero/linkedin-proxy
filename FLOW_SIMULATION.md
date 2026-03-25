# 🧠 Simulación Mental del Flujo Completo

## Escenario: Sincronización Completa LinkedIn → n8n

### **PASO 1: Startup del Gateway**

```
⏱️ Tiempo: 10:00:00

$ python3 main.py
🚀 Iniciando LinkedIn-n8n Gateway en http://localhost:8000
Dashboard: http://localhost:8000/admin
```

**Qué sucede:**
- FastAPI inicia en puerto 8000
- Carga config.json (si existe)
- Inicia logger a gateway.log
- Queda esperando peticiones

---

### **PASO 2: Configuración Inicial (Admin Dashboard)**

```
⏱️ Tiempo: 10:01:00

Usuario abre: http://localhost:8000/admin
```

**Dashboard muestra:**
```html
┌─────────────────────────────────────────┐
│   🔐 LinkedIn-n8n Gateway Admin         │
├─────────────────────────────────────────┤
│                                         │
│  LinkedIn Cookie (li_at)                │
│  [________________ input field _______] │
│                                         │
│  JSESSIONID Cookie                      │
│  [________________ input field _______] │
│                                         │
│  n8n Webhook URL                        │
│  [________________ input field _______] │
│                                         │
│  [💾 Guardar & Validar]                 │
│                                         │
└─────────────────────────────────────────┘
```

**Usuario ingresa:**
```
li_at: AQEDASxzw9YCxxxxxxxxxxxxxxxxxxxxxxx_xxxxx_xxxxxx_xxx_xxxxx
JSESSIONID: "AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
n8n_webhook_url: https://n8n.example.com/webhook/linkedin-sync
```

**Tiempo: 10:01:30 - Click en Guardar**

```
📥 POST /admin
└─ Body:
   - li_at: AQEDASxzw9YCxxxxxxxxxxxxxxxxxxxxxxx_xxxxx_xxxxxx_xxx_xxxxx
   - jsessionid: "AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   - n8n_webhook_url: https://n8n.example.com/webhook/linkedin-sync
```

**En el servidor:**

```
2024-03-20T10:01:30 - INFO - === SOLICITUD DE GUARDADO DE CONFIGURACIÓN ===
2024-03-20T10:01:30 - DEBUG - li_at: AQEDASxzw9YCx... (truncado)
2024-03-20T10:01:30 - INFO - Validando credenciales de LinkedIn...
```

**LIMPIEZA DE JSESSIONID:**
```
Entrada: "AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  ↓
strip()                 → AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (quita espacios)
  ↓
strip('"\'')            → AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (quita comillas)
  ↓
Resultado limpio: AQEDcwE3xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**VALIDACIÓN CON LINKEDIN:**
```
2024-03-20T10:01:31 - INFO - Conectando a LinkedIn...
2024-03-20T10:01:31 - INFO - Llamando get_profile()...

[LinkedIn API]
GET https://www.linkedin.com/voyager/api/me
Headers: 
  - Cookie: li_at=AQEDASxzw9YCx...
  - Cookie: JSESSIONID=AQEDcwE3xxx...
Response: 200 OK
```

**RESULTADO:**
```
Profile recibido:
{
  "firstName": "Hernan",
  "lastName": "García",
  "headline": "AI Engineer | Python Developer",
  "id": "xxxxxxxx"
}

2024-03-20T10:01:32 - INFO - ✓ Validación exitosa. 
                             Perfil: Hernan
```

**GUARDADO:**
```
📝 Escribiendo config.json:
{
  "li_at": "AQEDASxzw9YCx...",
  "jsessionid": "AQEDcwE3xxx...",
  "n8n_webhook_url": "https://n8n.example.com/webhook/linkedin-sync",
  "last_sync": "2024-03-20T10:01:32"
}

2024-03-20T10:01:32 - INFO - Configuración guardada exitosamente
```

**Browser recibe:**
```html
✅ Configuración Guardada
Las cookies fueron validadas correctamente.
[← Volver al dashboard]
```

---

### **PASO 3: Sincronización desde n8n (Webhook)**

```
⏱️ Tiempo: 10:15:00

n8n ejecuta: POST http://localhost:8000/sync
```

**En el servidor:**

```
2024-03-20T10:15:00 - INFO - === INICIANDO SINCRONIZACIÓN ===
2024-03-20T10:15:00 - INFO - Request recibido: POST /sync
```

**Cargar configuración:**
```
📂 Leyendo config.json...
✓ Config cargada:
  - li_at: ✓ configurado
  - jsessionid: ✓ configurado
  - n8n_webhook_url: ✓ configurado
```

**Conectar a LinkedIn:**
```
2024-03-20T10:15:01 - INFO - Conectando a LinkedIn...

[LinkedIn API]
client = Linkedin(
  li_at="AQEDASxzw9YCx...",
  jsessionid="AQEDcwE3xxx..."
)
✓ Conexión exitosa
```

**Obtener conversaciones:**
```
2024-03-20T10:15:02 - INFO - Obteniendo conversaciones...

[LinkedIn API]
GET /voyager/api/messaging/conversations?start=0&count=50
Response: 200 OK

Conversaciones encontradas:
[
  {
    "conversationId": "conv_12345",
    "participantName": "John Doe",
    "messages": [
      {
        "messageId": "msg_001",
        "text": "Hola Hernan, ¿cómo estás?",
        "from": "John Doe",
        "timestamp": "2024-03-20T10:10:00Z"
      },
      {
        "messageId": "msg_002",
        "text": "¿Podrías ayudarme con un proyecto?",
        "from": "John Doe",
        "timestamp": "2024-03-20T10:11:00Z"
      }
    ]
  },
  {
    "conversationId": "conv_67890",
    "participantName": "Jane Smith",
    "messages": [
      {
        "messageId": "msg_003",
        "text": "Excelente propuesta, me interesa",
        "from": "Jane Smith",
        "timestamp": "2024-03-20T10:12:00Z"
      }
    ]
  }
]
```

**Cargar mensajes procesados:**
```
2024-03-20T10:15:03 - INFO - Cargando processed_messages.json...

processed_ids = {
  "msg_001",
  "msg_002"
}

(Estos ya fueron procesados antes)
```

**Identificar mensajes nuevos:**
```
2024-03-20T10:15:03 - INFO - Comparando con processed_ids...

msg_001: ¿En processed_ids?  ✓ SÍ → Saltar
msg_002: ¿En processed_ids?  ✓ SÍ → Saltar
msg_003: ¿En processed_ids?  ✗ NO → NUEVO! ➕

Mensajes nuevos para enviar: 1
```

**Transformar para n8n:**
```
2024-03-20T10:15:04 - INFO - Transformando para n8n...

LinkedIn message:
{
  "messageId": "msg_003",
  "conversationId": "conv_67890",
  "text": "Excelente propuesta, me interesa",
  "from": "Jane Smith",
  "timestamp": "2024-03-20T10:12:00Z"
}
       ↓↓↓
    TRANSFORMA
       ↓↓↓
n8n payload:
{
  "conversation_id": "conv_67890",
  "message_id": "msg_003",
  "text": "Excelente propuesta, me interesa",
  "sender": "Jane Smith",
  "timestamp": "2024-03-20T10:12:00Z",
  "gateway_timestamp": "2024-03-20T10:15:04.123456"
}
```

**Enviar a n8n webhook:**
```
2024-03-20T10:15:04 - INFO - Enviando 1 mensajes a n8n...

POST https://n8n.example.com/webhook/linkedin-sync
Headers:
  - Content-Type: application/json

Body:
{
  "action": "sync_messages",
  "messages": [
    {
      "conversation_id": "conv_67890",
      "message_id": "msg_003",
      "text": "Excelente propuesta, me interesa",
      "sender": "Jane Smith",
      "timestamp": "2024-03-20T10:12:00Z",
      "gateway_timestamp": "2024-03-20T10:15:04.123456"
    }
  ],
  "timestamp": "2024-03-20T10:15:04.123456"
}

[Esperando respuesta...]
```

**n8n responde:**
```
Response: 200 OK

Body:
{
  "status": "success",
  "processed": 1,
  "workflowId": "wf_xyz123"
}

2024-03-20T10:15:05 - INFO - Respuesta de n8n: 200
2024-03-20T10:15:05 - DEBUG - Body: {"status": "success", ...}
```

**Marcar como procesados:**
```
2024-03-20T10:15:05 - INFO - Actualizando processed_messages.json...

processed_ids.add("msg_003")

processed_messages.json:
{
  "processed_ids": [
    "msg_001",
    "msg_002",
    "msg_003"
  ]
}
```

**Responder a n8n:**
```
Response 200 OK:
{
  "status": "success",
  "messages_synced": 1,
  "n8n_response": {
    "status": "success",
    "processed": 1,
    "workflowId": "wf_xyz123"
  }
}

2024-03-20T10:15:05 - INFO - ✓ Sincronización completada exitosamente
```

---

### **PASO 4: Rate Limit (429) - Reintento Automático**

```
⏱️ Tiempo: 10:25:00

n8n intenta /sync pero LinkedIn está bajo presión
```

**Primer intento:**
```
2024-03-20T10:25:00 - INFO - Conectando a LinkedIn...
[LinkedIn API]
GET /voyager/api/messaging/conversations
Response: 429 Too Many Requests

2024-03-20T10:25:00 - WARNING - Rate limit (429) en sync. 
                               Reintentando en 1s (intento 1/3)
```

**Esperar 1 segundo:**
```
[Esperando 1s...]
```

**Segundo intento:**
```
2024-03-20T10:25:01 - INFO - Conectando a LinkedIn...
[LinkedIn API]
GET /voyager/api/messaging/conversations
Response: 429 Too Many Requests

2024-03-20T10:25:01 - WARNING - Rate limit (429) en sync. 
                               Reintentando en 2s (intento 2/3)
```

**Esperar 2 segundos:**
```
[Esperando 2s...]
```

**Tercer intento:**
```
2024-03-20T10:25:03 - INFO - Conectando a LinkedIn...
[LinkedIn API]
GET /voyager/api/messaging/conversations
Response: 200 OK ✓

2024-03-20T10:25:03 - INFO - ✓ Sincronización completada exitosamente
```

---

### **PASO 5: Responder desde n8n**

```
⏱️ Tiempo: 10:30:00

n8n ejecuta: POST /reply
```

**Request:**
```
POST http://localhost:8000/reply
Body:
{
  "conversation_id": "conv_67890",
  "text": "¡Gracias por tu interés! Vamos a coordinar una llamada."
}

2024-03-20T10:30:00 - INFO - === ENVIANDO RESPUESTA ===
2024-03-20T10:30:00 - INFO - Conversación: conv_67890
2024-03-20T10:30:00 - INFO - Texto: ¡Gracias por tu interés! Vamos a coordinara una llamada.
```

**Conectar a LinkedIn:**
```
client = Linkedin(...)
✓ Autenticado
```

**Enviar mensaje:**
```
2024-03-20T10:30:01 - INFO - Intentando enviar mensaje...

POST /voyager/api/messaging/conversations/conv_67890/messages
Body:
{
  "text": "¡Gracias por tu interés! Vamos a coordinar una llamada.",
  "mediaCollections": []
}

Response: 201 Created
Message ID: msg_response_001
```

**Responder a n8n:**
```
Response 200 OK:
{
  "status": "sent",
  "conversation_id": "conv_67890",
  "message_id": "msg_response_001",
  "timestamp": "2024-03-20T10:30:01.456789"
}

2024-03-20T10:30:01 - INFO - ✓ Respuesta enviada: {"status": "sent", ...}
```

---

### **PASO 6: Cookie Expirada (Error 401)**

```
⏱️ Tiempo: 11:00:00 (1 hora después)

Usuario intenta guardar nuevamente (cookies expiradas)
```

**Request:**
```
POST /admin
Body:
{
  "li_at": "AQEDASxzw9YCx... (LA MISMA COOKIE DE ANTES)",
  "jsessionid": "AQEDcwE3xxx...",
  "n8n_webhook_url": "..."
}
```

**Validación:**
```
2024-03-20T11:00:00 - INFO - Validando credenciales de LinkedIn...

client = Linkedin(li_at, jsessionid)
GET https://www.linkedin.com/voyager/api/me
Response: 401 Unauthorized

2024-03-20T11:00:01 - ERROR - ✗ Error de validación: 401 Unauthorized
2024-03-20T11:00:01 - ERROR - Detectado: Cookie expirada
```

**Respuesta al usuario:**
```html
400 Bad Request

❌ Error de Validación
Cookie expirada o inválida (401)

[← Volver al dashboard]
```

**Usuario debe regenerar cookies en LinkedIn y reintentar.**

---

## 📊 Resumen del Flujo

```
CONFIGURACIÓN
  ├─ Admin abre dashboard
  ├─ Ingresa cookies + webhook_url
  ├─ Gateway valida con LinkedIn
  ├─ Si ✓ → Guarda en config.json
  └─ Si ✗ → Muestra error

SINCRONIZACIÓN PERIÓDICA
  ├─ n8n → POST /sync
  ├─ Gateway carga config.json
  ├─ Conecta a LinkedIn
  ├─ Obtiene conversaciones
  ├─ Compara con processed_messages.json
  ├─ Identifica mensajes nuevos
  ├─ Transforma para n8n
  ├─ Envía a webhook
  ├─ Actualiza processed_messages.json
  └─ Responde con resumen

RESPUESTAS
  ├─ n8n → POST /reply
  ├─ Gateway conecta a LinkedIn
  ├─ Envía mensaje a conversación
  └─ Responde con confirmación

MANEJO DE ERRORES
  ├─ 429 (Rate Limit) → Reintentos exponenciales
  ├─ 401 (Expirado) → Notificar al usuario
  ├─ 403 (Permisos) → Verificar cuenta
  └─ Otros → Loguear y responder error
```

---

**Tiempo total estimado por ciclo:** 1-5 segundos  
**Logs guardados en:** gateway.log  
**Estado de mensajes:** processed_messages.json  
**Configuración:** config.json
