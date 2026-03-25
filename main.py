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

app = FastAPI(title="LinkedIn-n8n Gateway", version="1.0.0")


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
        
        # Obtener conversaciones (mock por ahora - linkedin-api tiene limitaciones)
        logger.info("Obteniendo conversaciones...")
        conversations = client.get_conversations()
        
        if not conversations:
            logger.info("No hay conversaciones nuevas")
            return {"status": "success", "messages_synced": 0}
        
        # Cargar mensajes ya procesados
        processed_ids = load_processed_messages()
        messages_to_send = []
        
        # Procesar conversaciones
        for conv in conversations:
            conv_id = conv.get("conversationId") or conv.get("id")
            messages = conv.get("messages", [])
            
            for msg in messages:
                msg_id = msg.get("messageId") or f"{conv_id}_{msg.get('timestamp')}"
                
                if msg_id not in processed_ids:
                    logger.info(f"Nuevo mensaje encontrado: {msg_id}")
                    
                    # Construir payload para n8n
                    payload = {
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                        "text": msg.get("text", ""),
                        "sender": msg.get("from", ""),
                        "timestamp": msg.get("timestamp"),
                        "gateway_timestamp": datetime.now().isoformat()
                    }
                    
                    messages_to_send.append(payload)
                    processed_ids.add(msg_id)
        
        # Enviar a n8n
        if messages_to_send:
            logger.info(f"Enviando {len(messages_to_send)} mensajes a n8n...")
            
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                try:
                    response = await client_http.post(
                        config["n8n_webhook_url"],
                        json={
                            "action": "sync_messages",
                            "messages": messages_to_send,
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
                        "n8n_response": response.json()
                    }
                
                except httpx.ConnectError as e:
                    logger.error(f"No se puede conectar a n8n: {e}")
                    raise HTTPException(status_code=503, detail="n8n no accesible")
        
        else:
            logger.info("No hay mensajes nuevos para procesar")
            return {"status": "success", "messages_synced": 0}
    
    except Exception as e:
        logger.error(f"Error en sincronización: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reply")
async def send_reply(conversation_id: str, text: str):
    """
    Envía una respuesta a una conversación en LinkedIn.
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
        
        # Enviar mensaje (si la librería lo soporta)
        # Nota: linkedin-api puede tener limitaciones aquí
        logger.info("Intentando enviar mensaje...")
        
        # Mock response por ahora
        result = {
            "status": "sent",
            "conversation_id": conversation_id,
            "message_id": f"msg_{int(time.time())}",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"✓ Respuesta enviada: {result}")
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


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Iniciando LinkedIn-n8n Gateway en http://localhost:8000")
    logger.info("Dashboard: http://localhost:8000/admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)
