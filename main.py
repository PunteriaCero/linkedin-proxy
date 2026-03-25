"""
LinkedIn-n8n Gateway Microservice
Sincroniza mensajes de LinkedIn hacia n8n usando cookies de sesión.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
import time
from functools import wraps

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
from linkedin_api import Linkedin

# ===== CONFIGURACIÓN LOGGING =====
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== PATHS Y CONSTANTES =====
CONFIG_FILE = "config.json"
PROCESSED_MESSAGES_FILE = "processed_messages.json"
DEFAULT_CONFIG = {
    "li_at": "",
    "jsessionid": "",
    "n8n_webhook_url": "",
    "last_sync": None
}

app = FastAPI(
    title="LinkedIn-n8n Gateway",
    version="1.0.0",
    description="Microservicio FastAPI que sincroniza mensajes de LinkedIn hacia n8n usando cookies de sesión",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ===== UTILIDADES =====
def load_config() -> Dict[str, Any]:
    """Carga la configuración desde config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error al parsear {CONFIG_FILE}, usando default")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Guarda la configuración en config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    logger.info("Configuración guardada exitosamente")


def load_processed_messages() -> set:
    """Carga los IDs de mensajes ya procesados."""
    if os.path.exists(PROCESSED_MESSAGES_FILE):
        try:
            with open(PROCESSED_MESSAGES_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get("processed_ids", []))
        except json.JSONDecodeError:
            logger.error(f"Error al parsear {PROCESSED_MESSAGES_FILE}")
            return set()
    return set()


def save_processed_messages(processed_ids: set) -> None:
    """Guarda los IDs de mensajes procesados."""
    with open(PROCESSED_MESSAGES_FILE, 'w') as f:
        json.dump({"processed_ids": list(processed_ids)}, f, indent=2)


def clean_jsessionid(jsessionid: str) -> str:
    """Limpia caracteres extra de JSESSIONID (comillas, espacios)."""
    return jsessionid.strip().strip('"\'')


def retry_on_429(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator para reintentos exponenciales en 429."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except HTTPException as e:
                    if e.status_code == 429:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Rate limit (429) en {func.__name__}. "
                                f"Reintentando en {delay}s (intento {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            delay *= 2  # backoff exponencial
                        else:
                            logger.error(f"Max retries alcanzados para {func.__name__}")
                            raise
                    else:
                        raise
            return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except HTTPException as e:
                    if e.status_code == 429:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Rate limit (429) en {func.__name__}. "
                                f"Reintentando en {delay}s (intento {attempt + 1}/{max_retries})"
                            )
                            time.sleep(delay)
                            delay *= 2
                        else:
                            logger.error(f"Max retries alcanzados para {func.__name__}")
                            raise
                    else:
                        raise
            return None
        
        # Detectar si es async o sync
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ===== VALIDACIÓN DE LINKEDIN =====
def validate_linkedin_cookies(li_at: str, jsessionid: str) -> tuple[bool, str]:
    """
    Valida que las cookies sean correctas llamando a get_profile().
    Retorna (is_valid, error_message)
    """
    logger.info("Iniciando validación de cookies de LinkedIn...")
    
    if not li_at or not jsessionid:
        return False, "li_at y JSESSIONID no pueden estar vacíos"
    
    try:
        # Limpiar JSESSIONID
        jsessionid_clean = clean_jsessionid(jsessionid)
        
        # Intentar conexión
        client = Linkedin(li_at, jsessionid_clean)
        profile = client.get_profile()
        
        if profile:
            logger.info(f"✓ Validación exitosa. Perfil: {profile.get('firstName', 'Unknown')}")
            return True, "Cookies válidas"
        else:
            return False, "Perfil vacío - posible cookie expirada"
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"✗ Error de validación: {error_msg}")
        
        # Detectar errores comunes
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Cookie expirada o inválida (401)"
        elif "403" in error_msg:
            return False, "Acceso denegado (403) - verifica permisos"
        elif "JSESSIONID" in error_msg:
            return False, "Estructura de JSESSIONID incorrecta"
        elif "429" in error_msg:
            return False, "Rate limit alcanzado - intenta más tarde"
        else:
            return False, f"Error de conexión: {error_msg}"


# ===== ENDPOINTS =====

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirige al dashboard."""
    return '<meta http-equiv="refresh" content="0;url=/admin">'


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Dashboard admin para configuración."""
    config = load_config()
    
    # Mostrar estado de validación
    validation_status = ""
    if config.get("li_at") and config.get("jsessionid"):
        is_valid, msg = validate_linkedin_cookies(
            config["li_at"],
            config["jsessionid"]
        )
        validation_status = f"""
        <div style="border: 2px solid {'green' if is_valid else 'red'}; padding: 10px; margin: 10px 0; border-radius: 4px;">
            <strong>Estado de validación:</strong> {msg}
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LinkedIn-n8n Gateway | Admin</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #0a66c2;
                margin-bottom: 20px;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                font-weight: bold;
                margin-bottom: 5px;
                color: #333;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
                font-family: monospace;
            }}
            textarea {{
                resize: vertical;
                min-height: 80px;
            }}
            button {{
                background: #0a66c2;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
            }}
            button:hover {{
                background: #004182;
            }}
            .info {{
                background: #e3f2fd;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                font-size: 14px;
                color: #1565c0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                text-align: center;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 LinkedIn-n8n Gateway</h1>
            
            <div class="info">
                ℹ️ Este panel configura la conexión entre LinkedIn y n8n usando cookies de sesión.
                Las cookies se validan automáticamente al guardar.
            </div>
            
            {validation_status}
            
            <form method="POST" action="/admin">
                <div class="form-group">
                    <label for="li_at">LinkedIn Cookie (li_at)</label>
                    <input type="password" id="li_at" name="li_at" value="{config.get('li_at', '')}" placeholder="Pega tu cookie li_at aquí" required>
                </div>
                
                <div class="form-group">
                    <label for="jsessionid">JSESSIONID Cookie</label>
                    <input type="password" id="jsessionid" name="jsessionid" value="{config.get('jsessionid', '')}" placeholder="Pega tu JSESSIONID aquí" required>
                </div>
                
                <div class="form-group">
                    <label for="n8n_webhook_url">n8n Webhook URL</label>
                    <input type="url" id="n8n_webhook_url" name="n8n_webhook_url" value="{config.get('n8n_webhook_url', '')}" placeholder="https://n8n.example.com/webhook/..." required>
                </div>
                
                <button type="submit">💾 Guardar & Validar</button>
            </form>
            
            <div class="footer">
                <p>Versión 1.0.0 | Logs: gateway.log</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@app.post("/admin")
async def save_config_endpoint(
    li_at: str = Form(...),
    jsessionid: str = Form(...),
    n8n_webhook_url: str = Form(...)
):
    """Endpoint POST para guardar configuración con validación."""
    logger.info("=== SOLICITUD DE GUARDADO DE CONFIGURACIÓN ===")
    
    # Limpiar inputs
    li_at = li_at.strip()
    jsessionid = clean_jsessionid(jsessionid)
    n8n_webhook_url = n8n_webhook_url.strip()
    
    # Validar LinkedIn
    logger.info("Validando credenciales de LinkedIn...")
    is_valid, validation_msg = validate_linkedin_cookies(li_at, jsessionid)
    
    if not is_valid:
        logger.error(f"Validación fallida: {validation_msg}")
        # Redirigir al dashboard con error
        return HTMLResponse(
            f"""
            <html>
            <body>
                <h1>❌ Error de Validación</h1>
                <p>{validation_msg}</p>
                <p><a href="/admin">← Volver al dashboard</a></p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    # Guardar configuración
    config = {
        "li_at": li_at,
        "jsessionid": jsessionid,
        "n8n_webhook_url": n8n_webhook_url,
        "last_sync": datetime.now().isoformat()
    }
    save_config(config)
    logger.info("✓ Configuración guardada exitosamente")
    
    # Redirigir al dashboard
    return HTMLResponse(
        """
        <html>
        <body>
            <h1>✅ Configuración Guardada</h1>
            <p>Las cookies fueron validadas correctamente.</p>
            <p><a href="/admin">← Volver al dashboard</a></p>
        </body>
        </html>
        """
    )


@app.post("/sync")
@retry_on_429(max_retries=3, base_delay=1.0)
async def sync_messages():
    """
    Sincroniza conversaciones nuevas desde LinkedIn hacia n8n.
    Obtiene detalles completos de cada conversación incluyendo mensajes.
    """
    logger.info("=== INICIANDO SINCRONIZACIÓN ===")
    
    config = load_config()
    
    # Validar configuración
    if not config.get("li_at") or not config.get("jsessionid"):
        logger.error("Cookies no configuradas")
        raise HTTPException(status_code=400, detail="Cookies no configuradas")
    
    if not config.get("n8n_webhook_url"):
        logger.error("Webhook URL no configurada")
        raise HTTPException(status_code=400, detail="Webhook URL no configurada")
    
    try:
        # Conectar a LinkedIn
        logger.info("Conectando a LinkedIn...")
        client = Linkedin(config["li_at"], clean_jsessionid(config["jsessionid"]))
        
        # Obtener conversaciones (solo metadatos)
        logger.info("Obteniendo conversaciones...")
        conversations = client.get_conversations()
        
        if not conversations:
            logger.info("No hay conversaciones nuevas")
            return {"status": "success", "messages_synced": 0}
        
        # Cargar mensajes ya procesados
        processed_ids = load_processed_messages()
        messages_to_send = []
        
        # Procesar cada conversación
        logger.info(f"Procesando {len(conversations)} conversaciones...")
        for conv in conversations:
            try:
                # Obtener ID y participante
                conv_id = conv.get("conversation_urn_id") or conv.get("urn_id")
                participants = conv.get("participants", [])
                participant_name = participants[0].get("name", "Unknown") if participants else "Unknown"
                
                if not conv_id:
                    logger.warning(f"Conversación sin ID: {conv}")
                    continue
                
                # Obtener detalles completos de la conversación (incluyendo mensajes)
                logger.debug(f"Obteniendo detalles de conversación: {conv_id}")
                try:
                    details = client.get_conversation_details(conv_id)
                except Exception as e:
                    logger.warning(f"No se pudo obtener detalles de {conv_id}: {e}")
                    continue
                
                # Procesar mensajes
                messages = details.get("messages", [])
                logger.debug(f"Conversación {conv_id} tiene {len(messages)} mensajes")
                
                for msg in messages:
                    # Generar ID único del mensaje
                    msg_timestamp = msg.get("created", str(int(time.time())))
                    msg_id = f"{conv_id}_{msg_timestamp}"
                    
                    if msg_id not in processed_ids:
                        logger.info(f"Nuevo mensaje encontrado: {msg_id}")
                        
                        # Construir payload para n8n con info REAL de LinkedIn
                        payload = {
                            "conversation_id": conv_id,
                            "message_id": msg_id,
                            "participant_name": participant_name,
                            "body": msg.get("body", ""),
                            "text": msg.get("body", ""),  # Alias para compatibilidad
                            "sender_id": msg.get("from", ""),
                            "is_outgoing": msg.get("is_outgoing", False),
                            "created_at": msg.get("created", ""),
                            "attachment_count": len(msg.get("attachments", [])),
                            "attachments": msg.get("attachments", []),
                            "gateway_timestamp": datetime.now().isoformat()
                        }
                        
                        messages_to_send.append(payload)
                        processed_ids.add(msg_id)
                        logger.debug(f"Payload agregado: {payload}")
                
            except Exception as e:
                logger.error(f"Error procesando conversación {conv.get('conversation_urn_id')}: {e}")
                continue
        
        # Enviar a n8n si hay mensajes nuevos
        if messages_to_send:
            logger.info(f"Enviando {len(messages_to_send)} mensajes a n8n...")
            
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                try:
                    response = await client_http.post(
                        config["n8n_webhook_url"],
                        json={
                            "action": "sync_messages",
                            "messages": messages_to_send,
                            "total": len(messages_to_send),
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    logger.info(f"Respuesta de n8n: {response.status_code}")
                    logger.debug(f"Body: {response.text}")
                    
                    if response.status_code >= 400:
                        logger.error(f"Error en n8n: {response.text}")
                        raise HTTPException(status_code=response.status_code, detail=response.text)
                    
                    # Marcar como procesados
                    save_processed_messages(processed_ids)
                    
                    return {
                        "status": "success",
                        "messages_synced": len(messages_to_send),
                        "conversations_processed": len(conversations),
                        "n8n_response": response.json()
                    }
                
                except httpx.ConnectError as e:
                    logger.error(f"No se puede conectar a n8n: {e}")
                    raise HTTPException(status_code=503, detail="n8n no accesible")
        
        else:
            logger.info("No hay mensajes nuevos para procesar")
            return {"status": "success", "messages_synced": 0, "conversations_processed": len(conversations)}
    
    except Exception as e:
        logger.error(f"Error en sincronización: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reply")
async def send_reply(conversation_id: str, text: str):
    """
    Envía una respuesta a una conversación en LinkedIn.
    Valida respuesta real del servidor de LinkedIn.
    """
    logger.info(f"=== ENVIANDO RESPUESTA ===")
    logger.info(f"Conversación: {conversation_id}")
    logger.info(f"Texto: {text[:50]}...")
    
    config = load_config()
    
    if not config.get("li_at") or not config.get("jsessionid"):
        logger.error("Cookies no configuradas")
        raise HTTPException(status_code=400, detail="Cookies no configuradas")
    
    try:
        client = Linkedin(config["li_at"], clean_jsessionid(config["jsessionid"]))
        
        # Enviar mensaje y capturar respuesta
        logger.info("Enviando mensaje a LinkedIn...")
        error = client.send_message(
            message_body=text,
            conversation_urn_id=conversation_id
        )
        
        if error:
            logger.error(f"Error en send_message: {error}")
            raise HTTPException(status_code=500, detail="Failed to send message to LinkedIn")
        
        # Si no hay error, el mensaje se envió correctamente
        result = {
            "status": "sent",
            "conversation_id": conversation_id,
            "message_sent": text,
            "timestamp": datetime.now().isoformat(),
            "linkedin_validated": True
        }
        
        logger.info(f"✓ Respuesta enviada exitosamente: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Error al enviar respuesta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    config = load_config()
    return {
        "status": "healthy",
        "configured": bool(config.get("li_at") and config.get("jsessionid")),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/config")
async def get_config():
    """Obtiene la configuración actual (sin exponer secretos)."""
    config = load_config()
    return {
        "has_li_at": bool(config.get("li_at")),
        "has_jsessionid": bool(config.get("jsessionid")),
        "n8n_webhook_url": config.get("n8n_webhook_url", ""),
        "last_sync": config.get("last_sync")
    }


@app.get("/logs", response_class=HTMLResponse)
async def get_logs(lines: int = 100):
    """
    Obtiene los últimos N logs del archivo gateway.log.
    
    Parámetros:
    - lines: Número de líneas a retornar (default: 100)
    """
    try:
        if not os.path.exists("gateway.log"):
            return "<pre>No logs yet</pre>"
        
        with open("gateway.log", "r") as f:
            all_lines = f.readlines()
        
        # Obtener las últimas N líneas
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Formatear como HTML
        log_content = "".join(last_lines)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gateway Logs</title>
            <style>
                body {{
                    font-family: monospace;
                    background: #1e1e1e;
                    color: #d4d4d4;
                    padding: 20px;
                    margin: 0;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: #0a66c2;
                    border-bottom: 2px solid #0a66c2;
                    padding-bottom: 10px;
                }}
                .controls {{
                    margin-bottom: 20px;
                }}
                .controls a {{
                    display: inline-block;
                    padding: 10px 15px;
                    background: #0a66c2;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-right: 10px;
                }}
                .controls a:hover {{
                    background: #004182;
                }}
                pre {{
                    background: #252526;
                    padding: 15px;
                    border-radius: 4px;
                    overflow-x: auto;
                    border-left: 4px solid #0a66c2;
                }}
                .info {{
                    color: #4ec9b0;
                }}
                .error {{
                    color: #f48771;
                }}
                .warning {{
                    color: #dcdcaa;
                }}
                .debug {{
                    color: #9cdcfe;
                }}
                .auto-refresh {{
                    color: #858585;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Gateway Logs</h1>
                <div class="controls">
                    <a href="/logs?lines=50">Last 50</a>
                    <a href="/logs?lines=100">Last 100</a>
                    <a href="/logs?lines=500">Last 500</a>
                    <a href="/logs?lines=1000">Last 1000</a>
                    <a href="/admin">← Dashboard</a>
                </div>
                <pre><code>{log_content}</code></pre>
                <div class="auto-refresh">
                    ⏱️ Showing last {len(last_lines)} of {len(all_lines)} lines
                    | Refresh the page to see new logs
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    except Exception as e:
        logger.error(f"Error al leer logs: {e}")
        return f"<pre>Error reading logs: {e}</pre>"


@app.get("/logs/json")
async def get_logs_json(lines: int = 100):
    """
    Obtiene los últimos N logs en formato JSON.
    Más eficiente para parsing programático.
    
    Parámetros:
    - lines: Número de líneas a retornar (default: 100)
    """
    try:
        if not os.path.exists("gateway.log"):
            return {"logs": [], "total": 0}
        
        with open("gateway.log", "r") as f:
            all_lines = f.readlines()
        
        # Obtener las últimas N líneas
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Parsear logs (formato: timestamp - level - message)
        parsed_logs = []
        for line in last_lines:
            line = line.strip()
            if line:
                parts = line.split(" - ", 2)
                if len(parts) >= 3:
                    parsed_logs.append({
                        "timestamp": parts[0],
                        "level": parts[1],
                        "message": parts[2]
                    })
                else:
                    parsed_logs.append({
                        "timestamp": "",
                        "level": "INFO",
                        "message": line
                    })
        
        return {
            "logs": parsed_logs,
            "total": len(all_lines),
            "returned": len(parsed_logs),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error al leer logs JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Iniciando LinkedIn-n8n Gateway en http://localhost:8000")
    logger.info("Dashboard: http://localhost:8000/admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)
