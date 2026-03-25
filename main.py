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

# ===== PATHS Y CONSTANTES (ANTES DE LOGGING) =====
# Usar rutas que respeten los VOLUMEs de Docker
if os.path.exists("/app/config"):
    # Ejecutando en Docker - usar rutas de volúmenes
    CONFIG_DIR = Path("/app/config")
    LOGS_DIR = Path("/app/logs")
    DATA_DIR = Path("/app/data")
else:
    # Desarrollo local - crear directorios en raíz
    CONFIG_DIR = Path("./config")
    LOGS_DIR = Path("./logs")
    DATA_DIR = Path("./data")

# Crear directorios si no existen
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Archivos de configuración y datos
CONFIG_FILE = str(CONFIG_DIR / "config.json")
PROCESSED_MESSAGES_FILE = str(DATA_DIR / "processed_messages.json")
LOG_FILE = str(LOGS_DIR / "gateway.log")

# ===== CONFIGURACIÓN LOGGING =====
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
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
    Valida que las cookies sean correctas.
    NOTA: La librería linkedin-api requiere pasar cookies como dict.
    Retorna (is_valid, error_message)
    """
    logger.info("=== INICIANDO VALIDACIÓN DE COOKIES ===")
    
    if not li_at or not jsessionid:
        return False, "li_at y JSESSIONID no pueden estar vacíos"
    
    # 1. VALIDAR ESTRUCTURA
    logger.info(f"Validando estructura: li_at ({len(li_at)} chars), JSESSIONID ({len(jsessionid)} chars)")
    
    if len(li_at) < 60:
        logger.error(f"li_at muy corta (mínimo 60 caracteres, tienes {len(li_at)})")
        return False, f"li_at cookie incompleta o incorrecta (tienes {len(li_at)} caracteres, se esperan 60+)"
    
    if len(jsessionid) < 20:
        logger.error(f"JSESSIONID muy corta (mínimo 20 caracteres, tienes {len(jsessionid)})")
        return False, f"JSESSIONID incompleta o incorrecta (tienes {len(jsessionid)} caracteres, se esperan 20+)"
    
    logger.info("✓ Estructura de cookies válida")
    
    try:
        # Limpiar JSESSIONID
        jsessionid_clean = clean_jsessionid(jsessionid)
        logger.info("Preparando cookies para LinkedIn...")
        
        # FORMATO CORRECTO: Pasar cookies como dict con authenticate=False
        cookies = {
            'li_at': li_at,
            'JSESSIONID': jsessionid_clean
        }
        
        logger.info("Conectando a LinkedIn...")
        # No pasar timeout (linkedin-api no lo soporta como parámetro)
        # No pasar username/password (usaremos authenticate=False)
        client = Linkedin(
            username='',  # dummy - no se usa con cookies
            password='',  # dummy - no se usa con cookies
            authenticate=False,  # No intentar autenticación
            cookies=cookies
        )
        
        logger.info("Intentando get_profile()...")
        profile = client.get_profile()
        
        if profile and profile.get('firstName'):
            name = profile.get('firstName', 'Unknown')
            logger.info(f"✓ Validación exitosa. Perfil: {name}")
            return True, "Cookies válidas"
        elif profile:
            logger.warning("Perfil retornado pero sin firstName")
            return True, "Cookies válidas (perfil obtenido)"
        else:
            logger.warning("Perfil vacío retornado")
            return False, "Perfil vacío - posible cookie expirada"
    
    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        logger.error(f"✗ Error de validación: {error_msg}")
        
        # DETECTAR Y CLASIFICAR ERRORES
        
        if "challenge" in error_lower:
            logger.error(">>> CHALLENGE DETECTADO <<<")
            return False, (
                "LinkedIn requiere verificación adicional (CHALLENGE). "
                "Esto ocurre cuando LinkedIn detecta actividad inusual. "
                "Posibles soluciones:\n"
                "1) Abre LinkedIn en tu navegador y completa cualquier verificación\n"
                "2) Si te pide código de verificación (email/teléfono), complétalo\n"
                "3) Espera 5-10 minutos\n"
                "4) Regenera las cookies\n"
                "5) Intenta nuevamente"
            )
        
        elif "401" in error_msg or "unauthorized" in error_lower:
            logger.error(">>> 401 UNAUTHORIZED <<<")
            return False, "Cookie expirada o inválida (Error 401). Intenta regenerar las cookies."
        
        elif "403" in error_msg:
            logger.error(">>> 403 FORBIDDEN <<<")
            return False, "Acceso denegado (Error 403). Verifica permisos de cuenta."
        
        elif "jsessionid" in error_lower:
            logger.error(">>> JSESSIONID ERROR <<<")
            return False, "Estructura de JSESSIONID incorrecta. Cópiala nuevamente desde DevTools."
        
        elif "429" in error_msg:
            logger.error(">>> 429 RATE LIMIT <<<")
            return False, "Rate limit alcanzado (Error 429). Intenta más tarde."
        
        elif "connection" in error_lower or "timeout" in error_lower or "connect" in error_lower:
            logger.error(">>> CONNECTION ERROR <<<")
            return False, (
                "No se puede conectar a LinkedIn. "
                "Posibles causas:\n"
                "1) Problema de conexión de red\n"
                "2) LinkedIn no disponible\n"
                "3) Bloqueo de IP\n"
                "4) Cookies expiradas\n\n"
                "Intenta: Verifica conexión, abre LinkedIn en navegador, regenera cookies"
            )
        
        else:
            logger.error(f">>> ERROR DESCONOCIDO: {error_msg} <<<")
            return False, (
                f"Error de validación: {error_msg[:80]}\n"
                "Recomendaciones:\n"
                "1) Verifica que ambas cookies sean correctas\n"
                "2) Cópiala completamente desde DevTools\n"
                "3) Regenera las cookies desde LinkedIn"
            )


# ===== ENDPOINTS =====

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirige al dashboard."""
    return '<meta http-equiv="refresh" content="0;url=/admin">'


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Dashboard admin para configuración."""
    config = load_config()
    
    # Mostrar estado de validación basado en config guardada
    validation_status = ""
    status_flag = config.get("validation_status", "unknown")
    
    if config.get("li_at") and config.get("jsessionid"):
        # Mostrar estado del último intento de validación
        if status_flag == "valid":
            validation_status = """
            <div style="border: 2px solid #4caf50; background: #f1f8e9; padding: 15px; margin: 10px 0; border-radius: 4px;">
                <strong style="color: #2e7d32;">✅ Validación: EXITOSA</strong>
                <p style="margin: 5px 0; color: #558b2f; font-size: 14px;">Las cookies están configuradas y validadas.</p>
            </div>
            """
        elif status_flag == "failed":
            error_msg = config.get("validation_error", "Error desconocido")
            validation_status = f"""
            <div style="border: 2px solid #f44336; background: #ffebee; padding: 15px; margin: 10px 0; border-radius: 4px;">
                <strong style="color: #c62828;">❌ Validación: FALLIDA</strong>
                <p style="margin: 5px 0; color: #b71c1c; font-size: 14px;">{error_msg}</p>
                <p style="margin: 5px 0; color: #666; font-size: 12px;">💡 Intenta actualizar las cookies y validar nuevamente.</p>
            </div>
            """
        elif status_flag == "pending":
            validation_status = """
            <div style="border: 2px solid #ff9800; background: #fff3e0; padding: 15px; margin: 10px 0; border-radius: 4px;">
                <strong style="color: #e65100;">⏳ Validación: PENDIENTE</strong>
                <p style="margin: 5px 0; color: #bf360c; font-size: 14px;">Los datos se guardaron pero aún no se validaron.</p>
            </div>
            """
        else:
            validation_status = """
            <div style="border: 2px solid #9c27b0; background: #f3e5f5; padding: 15px; margin: 10px 0; border-radius: 4px;">
                <strong style="color: #6a1b9a;">ℹ️ Validación: NO REALIZADA</strong>
                <p style="margin: 5px 0; color: #7b1fa2; font-size: 14px;">Ingresa cookies para comenzar.</p>
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
                    <input type="text" id="li_at" name="li_at" value="{config.get('li_at', '')}" placeholder="Pega tu cookie li_at aquí" required>
                    <small style="color: #666;">Visible para facilitar copiar/pegar</small>
                </div>
                
                <div class="form-group">
                    <label for="jsessionid">JSESSIONID Cookie</label>
                    <input type="text" id="jsessionid" name="jsessionid" value="{config.get('jsessionid', '')}" placeholder="Pega tu JSESSIONID aquí" required>
                    <small style="color: #666;">Visible para facilitar copiar/pegar</small>
                </div>
                
                <div class="form-group">
                    <label for="n8n_webhook_url">n8n Webhook URL <span style="color: #999;">(Opcional)</span></label>
                    <input type="text" id="n8n_webhook_url" name="n8n_webhook_url" value="{config.get('n8n_webhook_url', '')}" placeholder="https://n8n.example.com/webhook/...">
                    <small style="color: #666;">Si no lo configuras, la sincronización estará deshabilitada</small>
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
    n8n_webhook_url: str = Form(default="")
):
    """Endpoint POST para guardar configuración con validación."""
    logger.info("=== SOLICITUD DE GUARDADO DE CONFIGURACIÓN ===")
    
    # Limpiar inputs
    li_at = li_at.strip()
    jsessionid = clean_jsessionid(jsessionid)
    n8n_webhook_url = n8n_webhook_url.strip()
    
    # GUARDAR PRIMERO - independiente de validación
    # Esto permite que el usuario vea qué valores estaba intentando guardar
    config_to_save = {
        "li_at": li_at,
        "jsessionid": jsessionid,
        "n8n_webhook_url": n8n_webhook_url if n8n_webhook_url else "",
        "last_sync": datetime.now().isoformat(),
        "validation_status": "pending"  # Marcar como pendiente validación
    }
    save_config(config_to_save)
    logger.info("✓ Datos guardados en config (pendiente validación)")
    
    # VALIDAR DESPUÉS
    logger.info("Validando credenciales de LinkedIn...")
    is_valid, validation_msg = validate_linkedin_cookies(li_at, jsessionid)
    
    if not is_valid:
        logger.error(f"Validación fallida: {validation_msg}")
        logger.info("⚠️  Los datos se guardaron pero la validación falló")
        
        # Marcar config como inválida
        config_to_save["validation_status"] = "failed"
        config_to_save["validation_error"] = validation_msg
        save_config(config_to_save)
        
        # Mostrar error pero permitir revisión de datos guardados
        return HTMLResponse(
            f"""
            <html>
            <head>
                <style>
                    body {{ font-family: sans-serif; margin: 50px; }}
                    .error {{ color: #d32f2f; margin: 20px 0; }}
                    .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                    a {{ color: #0a66c2; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <h1 class="error">❌ Validación Fallida</h1>
                <div class="warning">
                    <strong>⚠️  Los datos se han guardado, pero la validación falló:</strong><br><br>
                    {validation_msg}
                </div>
                <p>Por favor, verifica que tus cookies sean correctas y aún sean válidas.</p>
                <p style="color: #666; font-size: 14px;">
                    💡 Puedes ver los valores guardados en el formulario. Intenta actualizar las cookies y vuelve a intentar.
                </p>
                <p><a href="/admin">← Volver al dashboard</a></p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    # VALIDACIÓN EXITOSA - Marcar como válida
    config_to_save["validation_status"] = "valid"
    config_to_save.pop("validation_error", None)
    save_config(config_to_save)
    
    logger.info("✓ Configuración guardada Y validada exitosamente")
    logger.info(f"  - LinkedIn cookies: ✓ validadas")
    logger.info(f"  - n8n webhook: {'configurado' if n8n_webhook_url else 'no configurado (sincronización deshabilitada)'}")
    
    # Redirigir al dashboard
    return HTMLResponse(
        """
        <html>
        <head>
            <style>
                body { font-family: sans-serif; margin: 50px; }
                .success { color: #388e3c; }
                a { color: #0a66c2; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <h1 class="success">✅ Configuración Guardada y Validada</h1>
            <p>Las cookies fueron validadas correctamente y guardadas.</p>
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
    NOTA: El webhook de n8n debe estar configurado para que funcione.
    """
    logger.info("=== INICIANDO SINCRONIZACIÓN ===")
    
    config = load_config()
    
    # Validar configuración
    if not config.get("li_at") or not config.get("jsessionid"):
        logger.error("Cookies no configuradas")
        raise HTTPException(status_code=400, detail="Cookies no configuradas")
    
    # WEBHOOK ES OPCIONAL - pero necesario para sincronizar
    if not config.get("n8n_webhook_url"):
        logger.warning("Webhook de n8n no configurado - sincronización deshabilitada")
        raise HTTPException(
            status_code=400, 
            detail="Webhook de n8n no configurado. Configúralo en /admin para habilitar la sincronización."
        )
    
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
