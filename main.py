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
from pydantic import BaseModel
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

# ===== MODELOS PYDANTIC =====
class ValidateCookiesRequest(BaseModel):
    """Request model para POST /validate-cookies"""
    li_at: str
    jsessionid: str
    bcookie: str = ""
    lidc: str = ""
    user_match_history: str = ""
    aam_uuid: str = ""

DEFAULT_CONFIG = {
    "li_at": "",
    "jsessionid": "",
    "bcookie": "",  # Browser cookie (IMPORTANTE)
    "lidc": "",  # LinkedIn data center (IMPORTANTE)
    "user_match_history": "",  # Tracking cookie
    "aam_uuid": "",  # Audience Manager UUID
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


def create_linkedin_client_with_cookies(li_at: str, jsessionid: str, bcookie: str = "", lidc: str = "", **kwargs):
    """
    Crea un cliente de LinkedIn con cookies y aplica el workaround necesario
    para asegurar que se establezcan correctamente.
    
    :param li_at: Cookie li_at
    :param jsessionid: Cookie JSESSIONID
    :param bcookie: Cookie bcookie (opcional)
    :param lidc: Cookie lidc (opcional)
    :param kwargs: Otras cookies opcionales
    :return: Cliente de LinkedIn configurado correctamente
    """
    jsessionid_clean = clean_jsessionid(jsessionid)
    
    # Preparar diccionario de cookies
    cookies = {
        'li_at': li_at,
        'JSESSIONID': jsessionid_clean
    }
    
    if bcookie:
        cookies['bcookie'] = bcookie
    if lidc:
        cookies['lidc'] = lidc
    if kwargs.get('user_match_history'):
        cookies['UserMatchHistory'] = kwargs['user_match_history']
    if kwargs.get('aam_uuid'):
        cookies['aam_uuid'] = kwargs['aam_uuid']
    
    # Crear cliente
    client = Linkedin(
        username='',
        password='',
        authenticate=False,
        cookies=cookies
    )
    
    # WORKAROUND: Asegurar que cookies se establezcan correctamente
    if hasattr(client, 'client') and hasattr(client.client, 'session'):
        for key, value in cookies.items():
            client.client.session.cookies.set(key, value)
        
        # Establecer csrf-token
        csrf_token = jsessionid_clean.strip('"')
        client.client.session.headers["csrf-token"] = csrf_token
        logger.debug(f"✓ Cliente LinkedIn inicializado con {len(cookies)} cookies")
    
    return client


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
def validate_linkedin_cookies(li_at: str, jsessionid: str, bcookie: str = "", lidc: str = "", **kwargs) -> tuple[bool, str]:
    """
    Valida que las cookies sean correctas.
    Retorna (is_valid, error_message)
    
    :param li_at: Cookie li_at (requerida)
    :param jsessionid: Cookie JSESSIONID (requerida)
    :param bcookie: Cookie bcookie (opcional pero recomendada)
    :param lidc: Cookie lidc (opcional pero recomendada)
    :param kwargs: Otras cookies opcionales (user_match_history, aam_uuid, etc.)
    """
    is_valid, error_msg, _ = validate_linkedin_cookies_with_profile(li_at, jsessionid, bcookie, lidc, **kwargs)
    return is_valid, error_msg


def validate_linkedin_cookies_with_profile(li_at: str, jsessionid: str, bcookie: str = "", lidc: str = "", **kwargs) -> tuple[bool, str, dict]:
    """
    Valida que las cookies sean correctas y retorna el perfil del usuario.
    Retorna (is_valid, error_message, profile_data)
    
    profile_data contiene:
    - 'name': Nombre completo del usuario
    - 'profile': Objeto de perfil completo
    - 'updated_cookies': Cookies actualizadas por LinkedIn (para guardar)
    
    :param li_at: Cookie li_at (requerida)
    :param jsessionid: Cookie JSESSIONID (requerida)
    :param bcookie: Cookie bcookie (opcional pero recomendada)
    :param lidc: Cookie lidc (opcional pero recomendada)
    :param kwargs: Otras cookies opcionales (user_match_history, aam_uuid, etc.)
    """
    logger.info("=== INICIANDO VALIDACIÓN DE COOKIES ===")
    
    if not li_at or not jsessionid:
        return False, "li_at y JSESSIONID no pueden estar vacíos", {}
    
    # 1. VALIDAR ESTRUCTURA
    logger.info(f"Validando estructura: li_at ({len(li_at)} chars), JSESSIONID ({len(jsessionid)} chars)")
    logger.info(f"Cookies adicionales: bcookie ({len(bcookie)} chars), lidc ({len(lidc)} chars)")
    
    if len(li_at) < 60:
        logger.error(f"li_at muy corta (mínimo 60 caracteres, tienes {len(li_at)})")
        return False, f"li_at cookie incompleta (tienes {len(li_at)} caracteres, se esperan 60+)", {}
    
    if len(jsessionid) < 20:
        logger.error(f"JSESSIONID muy corta (mínimo 20 caracteres, tienes {len(jsessionid)})")
        return False, f"JSESSIONID incompleta (tienes {len(jsessionid)} caracteres, se esperan 20+)", {}
    
    logger.info("✓ Estructura de cookies válida")
    
    try:
        # Limpiar JSESSIONID
        jsessionid_clean = clean_jsessionid(jsessionid)
        logger.info("Preparando cookies para LinkedIn...")
        
        # Pasar TODAS las cookies disponibles (no solo 2)
        cookies = {
            'li_at': li_at,
            'JSESSIONID': jsessionid_clean
        }
        
        # Agregar cookies opcionales si están disponibles
        if bcookie:
            cookies['bcookie'] = bcookie
            logger.info(f"✓ bcookie agregada ({len(bcookie)} chars)")
        
        if lidc:
            cookies['lidc'] = lidc
            logger.info(f"✓ lidc agregada ({len(lidc)} chars)")
        
        # Otras cookies opcionales del kwargs
        if 'user_match_history' in kwargs and kwargs['user_match_history']:
            cookies['UserMatchHistory'] = kwargs['user_match_history']
        
        if 'aam_uuid' in kwargs and kwargs['aam_uuid']:
            cookies['aam_uuid'] = kwargs['aam_uuid']
        
        logger.info(f"Total de cookies a enviar: {len(cookies)}")
        logger.debug(f"Cookies: {list(cookies.keys())}")
        
        logger.info("Conectando a LinkedIn...")
        client = create_linkedin_client_with_cookies(
            li_at, jsessionid_clean,
            bcookie=bcookie,
            lidc=lidc,
            **kwargs
        )
        
        logger.info("Intentando get_user_profile()...")
        profile = client.get_user_profile()
        
        if profile:
            # Obtener nombre del perfil
            first_name = profile.get('miniProfile', {}).get('firstName', 'Unknown')
            last_name = profile.get('miniProfile', {}).get('lastName', '')
            full_name = f"{first_name} {last_name}".strip() if first_name != 'Unknown' else 'Unknown'
            
            logger.info(f"✓ Validación exitosa. Perfil: {full_name}")
            logger.debug(f"Perfil data: {profile}")
            
            # 🔥 IMPORTANTE: Capturar cookies actualizadas por LinkedIn
            updated_cookies = {}
            if hasattr(client, 'client') and hasattr(client.client, 'session'):
                logger.info("Capturando cookies actualizadas...")
                for key, value in client.client.session.cookies.items():
                    updated_cookies[key] = value
                    logger.debug(f"Cookie actualizada: {key} = {value[:30]}...")
            
            return True, "Cookies válidas", {
                'name': full_name,
                'profile': profile,
                'updated_cookies': updated_cookies
            }
        else:
            logger.warning("Perfil vacío retornado")
            return False, "Perfil vacío - posible cookie expirada", {}
    
    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        logger.error(f"✗ Error de validación: {error_msg}")
        
        # DETECTAR Y CLASIFICAR ERRORES
        
        # JSONDecodeError = LinkedIn rechazó las cookies (respuesta vacía)
        if "jsondecodeerror" in error_lower or "expecting value" in error_lower:
            logger.error(">>> JSON DECODE ERROR (LinkedIn rechazó cookies) <<<")
            return False, (
                "LinkedIn rechazó las cookies (respuesta vacía). "
                "Posibles causas:\n"
                "1) Cookies expiradas (24-48 horas máximo)\n"
                "2) Cookies inválidas\n"
                "3) LinkedIn bloqueó el acceso\n"
                "4) Cookies obtenidas desde navegador incógnito\n\n"
                "Solución: Regenera las cookies desde LinkedIn en navegador normal"
            ), {}
        
        elif "challenge" in error_lower:
            logger.error(">>> CHALLENGE DETECTADO <<<")
            return False, (
                "LinkedIn requiere verificación adicional (CHALLENGE). "
                "Abre LinkedIn en navegador, completa verificación, luego regenera cookies."
            ), {}
        
        elif "401" in error_msg or "unauthorized" in error_lower:
            logger.error(">>> 401 UNAUTHORIZED <<<")
            return False, "Cookies expiradas o inválidas (401). Regenera desde LinkedIn.", {}
        
        elif "403" in error_msg:
            logger.error(">>> 403 FORBIDDEN <<<")
            return False, "Acceso denegado (403). Verifica permisos de cuenta o bloqueos.", {}
        
        elif "jsessionid" in error_lower:
            logger.error(">>> JSESSIONID ERROR <<<")
            return False, "Estructura de JSESSIONID incorrecta. Obtén nuevamente desde DevTools.", {}
        
        elif "429" in error_msg:
            logger.error(">>> 429 RATE LIMIT <<<")
            return False, "Rate limit alcanzado. Intenta más tarde.", {}
        
        elif "connection" in error_lower or "timeout" in error_lower or "connect" in error_lower:
            logger.error(">>> CONNECTION ERROR <<<")
            return False, (
                "No se puede conectar a LinkedIn. Causas posibles:\n"
                "1) Problema de conexión de red\n"
                "2) LinkedIn no disponible\n"
                "3) Bloqueo de IP\n"
                "4) Cookies expiradas\n\n"
                "Intenta: Verifica conexión, abre LinkedIn, regenera cookies"
            ), {}
        
        else:
            logger.error(f">>> ERROR DESCONOCIDO: {error_msg[:100]} <<<")
            return False, (
                f"Error durante validación: {error_msg[:80]}\n"
                "Intenta:\n"
                "1) Verifica ambas cookies son correctas\n"
                "2) Obtenlas completamente desde DevTools\n"
                "3) Regenera las cookies desde LinkedIn"
            ), {}


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
            
            <div class="curl-parser">
                <h3>🔗 Extraer Cookies desde cURL</h3>
                <form id="curl-form" style="margin: 20px 0;">
                    <textarea id="curl-input" placeholder="Pega aquí tu comando cURL completo (Copy as cURL desde DevTools)" style="width: 100%; height: 100px; padding: 10px; font-family: monospace; font-size: 12px;"></textarea>
                    <button type="button" onclick="parseCurl()" style="margin-top: 10px; padding: 10px 20px; background: #0a66c2; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        📋 Extraer Cookies
                    </button>
                </form>
                <div id="curl-result" style="display:none; margin: 15px 0; padding: 15px; background: #e8f5e9; border: 1px solid #4caf50; border-radius: 4px;">
                    <p id="curl-message" style="margin: 0 0 10px 0;"></p>
                    <button type="button" onclick="applyCookies()" style="padding: 8px 16px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        ✓ Aplicar Cookies al Formulario
                    </button>
                </div>
            </div>
            
            <hr style="margin: 30px 0;">
            
            <form method="POST" action="/admin">
                <h3>📝 Configuración Manual</h3>
                
                <div class="form-group">
                    <label for="li_at">LinkedIn Cookie (li_at) *</label>
                    <input type="text" id="li_at" name="li_at" value="{config.get('li_at', '')}" placeholder="Cookie li_at (required)" required>
                    <small style="color: #666;">Identificador de sesión principal</small>
                </div>
                
                <div class="form-group">
                    <label for="jsessionid">JSESSIONID Cookie *</label>
                    <input type="text" id="jsessionid" name="jsessionid" value="{config.get('jsessionid', '')}" placeholder="JSESSIONID (required)" required>
                    <small style="color: #666;">Cookie de sesión secundaria</small>
                </div>
                
                <div class="form-group">
                    <label for="bcookie">Browser Cookie (bcookie)</label>
                    <input type="text" id="bcookie" name="bcookie" value="{config.get('bcookie', '')}" placeholder="bcookie (recomendado)">
                    <small style="color: #666;">Identificación del navegador (RECOMENDADO)</small>
                </div>
                
                <div class="form-group">
                    <label for="lidc">LinkedIn Data Center (lidc)</label>
                    <input type="text" id="lidc" name="lidc" value="{config.get('lidc', '')}" placeholder="lidc (recomendado)">
                    <small style="color: #666;">Identificador de data center (RECOMENDADO)</small>
                </div>
                
                <div class="form-group">
                    <label for="user_match_history">User Match History</label>
                    <input type="text" id="user_match_history" name="user_match_history" value="{config.get('user_match_history', '')}" placeholder="UserMatchHistory (opcional)">
                    <small style="color: #666;">Cookie de seguimiento (opcional)</small>
                </div>
                
                <div class="form-group">
                    <label for="aam_uuid">AAM UUID</label>
                    <input type="text" id="aam_uuid" name="aam_uuid" value="{config.get('aam_uuid', '')}" placeholder="aam_uuid (opcional)">
                    <small style="color: #666;">Audience Manager UUID (opcional)</small>
                </div>
                
                <div class="form-group">
                    <label for="n8n_webhook_url">n8n Webhook URL <span style="color: #999;">(Opcional)</span></label>
                    <input type="text" id="n8n_webhook_url" name="n8n_webhook_url" value="{config.get('n8n_webhook_url', '')}" placeholder="https://n8n.example.com/webhook/...">
                    <small style="color: #666;">Si no lo configuras, la sincronización estará deshabilitada</small>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="submit" style="flex: 1; padding: 12px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                        💾 Guardar Configuración
                    </button>
                    <button type="button" onclick="validateCookies()" style="flex: 1; padding: 12px; background: #2196f3; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                        ✓ Validar Cookies
                    </button>
                </div>
            </form>
            
            <script>
                let extracted_cookies = {{}};
                
                async function parseCurl() {{
                    const curl_input = document.getElementById('curl-input').value;
                    if (!curl_input.trim()) {{
                        alert('Por favor pega un comando cURL');
                        return;
                    }}
                    
                    const formData = new FormData();
                    formData.append('curl_command', curl_input);
                    
                    try {{
                        const response = await fetch('/parse-curl', {{
                            method: 'POST',
                            body: formData
                        }});
                        
                        const data = await response.json();
                        const resultDiv = document.getElementById('curl-result');
                        const messageP = document.getElementById('curl-message');
                        
                        if (data.success) {{
                            extracted_cookies = data.cookies;
                            messageP.innerHTML = '✓ ' + data.message + '<br>Cookies encontradas: ' + Object.keys(data.cookies).join(', ');
                            resultDiv.style.display = 'block';
                        }} else {{
                            alert('Error: ' + data.error);
                            resultDiv.style.display = 'none';
                        }}
                    }} catch (error) {{
                        alert('Error parseando cURL: ' + error);
                    }}
                }}
                
                function applyCookies() {{
                    if (Object.keys(extracted_cookies).length === 0) {{
                        alert('No hay cookies extraídas');
                        return;
                    }}
                    
                    // Aplicar cookies al formulario
                    if (extracted_cookies.li_at) document.getElementById('li_at').value = extracted_cookies.li_at;
                    if (extracted_cookies.jsessionid) document.getElementById('jsessionid').value = extracted_cookies.jsessionid;
                    if (extracted_cookies.bcookie) document.getElementById('bcookie').value = extracted_cookies.bcookie;
                    if (extracted_cookies.lidc) document.getElementById('lidc').value = extracted_cookies.lidc;
                    if (extracted_cookies.user_match_history) document.getElementById('user_match_history').value = extracted_cookies.user_match_history;
                    if (extracted_cookies.aam_uuid) document.getElementById('aam_uuid').value = extracted_cookies.aam_uuid;
                    
                    alert('✓ Cookies aplicadas al formulario. Ahora haz click en "Guardar Configuración"');
                    document.getElementById('curl-result').style.display = 'none';
                }}
                
                async function validateCookies() {{
                    const li_at = document.getElementById('li_at').value.trim();
                    const jsessionid = document.getElementById('jsessionid').value.trim();
                    
                    if (!li_at || !jsessionid) {{
                        alert('❌ Debes ingresar li_at y JSESSIONID antes de validar');
                        return;
                    }}
                    
                    // Mostrar mensaje de carga
                    const btn = event.target;
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '⏳ Validando...';
                    btn.disabled = true;
                    
                    try {{
                        const response = await fetch('/validate-cookies', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{
                                li_at: li_at,
                                jsessionid: jsessionid,
                                bcookie: document.getElementById('bcookie').value.trim(),
                                lidc: document.getElementById('lidc').value.trim(),
                                user_match_history: document.getElementById('user_match_history').value.trim(),
                                aam_uuid: document.getElementById('aam_uuid').value.trim()
                            }})
                        }});
                        
                        const data = await response.json();
                        
                        if (data.success) {{
                            let message = '✅ Cookies validadas correctamente!\\n\\nUsuario: ' + (data.user_name || 'N/A');
                            
                            // Si cookies fueron actualizadas por LinkedIn
                            if (data.cookies_updated) {{
                                message += '\\n\\n🔄 Cookies actualizadas automáticamente:';
                                if (data.updated_fields) {{
                                    message += '\\n' + data.updated_fields.join(', ');
                                }}
                            }}
                            
                            alert(message);
                        }} else {{
                            alert('❌ Validación fallida:\\n\\n' + data.detail);
                        }}
                    }} catch (error) {{
                        alert('❌ Error durante la validación: ' + error);
                    }} finally {{
                        btn.innerHTML = originalText;
                        btn.disabled = false;
                    }}
                }}
            </script>
            
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
    bcookie: str = Form(default=""),
    lidc: str = Form(default=""),
    user_match_history: str = Form(default=""),
    aam_uuid: str = Form(default=""),
    n8n_webhook_url: str = Form(default="")
):
    """Endpoint POST para guardar configuración. 
    
    ⚠️  IMPORTANTE: NO valida contra LinkedIn en este endpoint.
    Razón: Si válidas aquí, LinkedIn detecta múltiples conexiones 
    desde diferentes IPs (tu navegador + servidor) e invalida las cookies 
    automáticamente por seguridad.
    
    Solución: Solo guardar, NO validar.
    """
    logger.info("=== SOLICITUD DE GUARDADO DE CONFIGURACIÓN ===")
    
    # Limpiar inputs
    li_at = li_at.strip()
    jsessionid = clean_jsessionid(jsessionid)
    bcookie = bcookie.strip()
    lidc = lidc.strip()
    user_match_history = user_match_history.strip()
    aam_uuid = aam_uuid.strip()
    n8n_webhook_url = n8n_webhook_url.strip()
    
    # GUARDAR - SIN VALIDAR CONTRA LINKEDIN
    config_to_save = {
        "li_at": li_at,
        "jsessionid": jsessionid,
        "bcookie": bcookie,
        "lidc": lidc,
        "user_match_history": user_match_history,
        "aam_uuid": aam_uuid,
        "n8n_webhook_url": n8n_webhook_url if n8n_webhook_url else "",
        "last_sync": datetime.now().isoformat(),
        "validation_status": "unverified"  # Cambiar a "unverified" en lugar de "pending"
    }
    save_config(config_to_save)
    logger.info("✓ Datos guardados en config (sin validación)")
    
    # Loguear qué cookies fueron provistas
    cookies_provided = []
    if li_at: cookies_provided.append("li_at")
    if jsessionid: cookies_provided.append("jsessionid")
    if bcookie: cookies_provided.append("bcookie")
    if lidc: cookies_provided.append("lidc")
    if user_match_history: cookies_provided.append("user_match_history")
    if aam_uuid: cookies_provided.append("aam_uuid")
    logger.info(f"Cookies proporcionadas: {', '.join(cookies_provided)}")
    
    # Mostrar mensaje de éxito
    return HTMLResponse(
        """
        <html>
        <head>
            <style>
                body { font-family: sans-serif; margin: 50px; }
                .success { color: #388e3c; background: #f1f8e9; padding: 20px; border-radius: 4px; }
                .info { background: #e3f2fd; border: 1px solid #2196f3; padding: 15px; border-radius: 4px; margin: 20px 0; }
                a { color: #0a66c2; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .warning { color: #f57c00; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1 class="success">✅ Configuración Guardada</h1>
            <div class="info">
                <strong>Las cookies han sido guardadas correctamente.</strong><br><br>
                <strong class="warning">⚠️  Nota importante:</strong><br>
                No se validan contra LinkedIn en este momento para evitar que 
                LinkedIn invalide las cookies (detecta múltiples IPs usando las mismas cookies).
                <br><br>
                <strong>¿Cómo verificar que funcionan?</strong><br>
                1. Cierra navegador completamente<br>
                2. Vuelve a iniciar sesión en LinkedIn (nuevas cookies)<br>
                3. Extrae nuevamente las cookies en el admin<br>
                4. O usa el endpoint GET /messages para testear directamente
            </div>
            <p><a href="/admin">← Volver al dashboard</a></p>
        </body>
        </html>
        """
    )


@app.post("/parse-curl")
async def parse_curl_endpoint(curl_command: str = Form(...)):
    """
    Parsea un comando cURL y extrae cookies + headers.
    Soporta múltiples formatos:
    - -H "Cookie: ..." (formato Chrome DevTools)
    - -b 'cookies' (formato curl estándar)
    - --cookie "..." (alias de -b)
    Maneja saltos de línea en el cURL
    """
    logger.info("=== PARSEANDO COMANDO cURL ===")
    
    try:
        # Normaliza espacios y saltos de línea
        curl_command = curl_command.strip()
        # Reemplaza saltos de línea con espacios para facilitar búsqueda
        curl_normalized = " ".join(curl_command.split())
        
        logger.info(f"cURL recibido (primeros 100 chars): {curl_command[:100]}...")
        logger.info(f"cURL normalizado (primeros 100 chars): {curl_normalized[:100]}...")
        
        import re
        
        cookies_string = None
        
        # MÉTODO MEJORADO: Busca -b y extrae cookies de forma robusta
        # Maneja: -b 'cookies...' o -b "cookies..." o -b cookies
        import re
        
        b_patterns = [
            # -b 'cookies' (con comilla simple)
            r"-b\s+'([^']+)'",
            # -b "cookies" (con comilla doble)
            r'-b\s+"([^"]+)"',
            # -b cookies (sin comillas, hasta el próximo flag o espacio)
            r"-b\s+([^\s-][^\s]*(?:\s+(?!-).*?)*)",
        ]
        
        for pattern in b_patterns:
            match = re.search(pattern, curl_normalized)
            if match:
                cookies_string = match.group(1)
                logger.info(f"✓ Formato detectado: -b (curl estándar)")
                logger.info(f"  Cookies extraídas: {len(cookies_string)} caracteres")
                break
        
        # Si no encuentra -b, intenta -H "Cookie:" (Chrome DevTools)
        if not cookies_string:
            h_patterns = [
                r"-H\s+['\"]Cookie:\s*([^'\"]+)['\"]",  # -H "Cookie: ..."
                r"-H\s+Cookie:\s*([^\s]+)",  # -H Cookie: ... (sin comillas)
                r"-H\s+'Cookie:\s*([^']+)'",  # -H 'Cookie: ...'
            ]
            
            for pattern in h_patterns:
                match = re.search(pattern, curl_normalized)
                if match:
                    cookies_string = match.group(1)
                    logger.info(f"✓ Formato detectado: -H (Chrome DevTools)")
                    break
        
        if not cookies_string:
            logger.warning("No se encontró información de cookies en cURL")
            logger.debug(f"cURL normalizado: {curl_normalized[:500]}...")
            return {
                "success": False,
                "error": "No se encontraron cookies. Soportamos -H 'Cookie: ...' y -b 'cookies'",
                "debug": f"Se analizó: {curl_normalized[:200]}..."
            }
        
        logger.info(f"Cookies encontradas (primeros 150): {cookies_string[:150]}...")
        
        # Parsear cookies individuales respetando comillas
        cookies = {}
        
        # Split por ; (cookies pueden tener comillas internas)
        cookie_pairs = cookies_string.split(';')
        logger.info(f"Split encontró {len(cookie_pairs)} pares potenciales")
        
        for idx, pair in enumerate(cookie_pairs):
            pair = pair.strip()
            if not pair or '=' not in pair:
                if pair:
                    logger.debug(f"  Par {idx} descartado (vacío o sin =): {pair[:40]}...")
                continue
            
            # Buscar el primer = para separar key y value
            eq_idx = pair.find('=')
            key = pair[:eq_idx].strip().lower()
            value = pair[eq_idx+1:].strip()
            
            # Limpia comillas si existen (pueden ser simples o dobles)
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            cookies[key] = value
            logger.debug(f"  Par {idx}: {key} = {value[:40]}...")
        
        logger.info(f"Total de pares parseados: {len(cookies)}")
        logger.info(f"Keys parseadas: {list(cookies.keys())}")
        
        # Mapear nombres de cookies (a minúsculas, normalizado)
        extracted = {
            "li_at": cookies.get('li_at', ''),
            "jsessionid": cookies.get('jsessionid', ''),
            "bcookie": cookies.get('bcookie', ''),
            "lidc": cookies.get('lidc', ''),
            "user_match_history": cookies.get('usermatchhistory', '') or cookies.get('user_match_history', ''),
            "aam_uuid": cookies.get('aam_uuid', ''),
        }
        
        # Filtrar cookies vacías
        extracted_clean = {k: v for k, v in extracted.items() if v}
        
        logger.info(f"Cookies extraídas: {list(extracted_clean.keys())}")
        logger.info(f"Total de cookies encontradas: {len(extracted_clean)}")
        
        # Log de debugging para cada cookie
        for key in extracted.keys():
            status = "✓" if extracted[key] else "✗"
            logger.debug(f"{status} {key}: {extracted[key][:50] if extracted[key] else 'NO ENCONTRADA'}...")
        
        return {
            "success": True,
            "cookies": extracted_clean,
            "message": f"✓ Se encontraron {len(extracted_clean)} cookies",
            "critical_cookies": {
                "li_at": bool(extracted_clean.get('li_at')),
                "jsessionid": bool(extracted_clean.get('jsessionid')),
                "bcookie": bool(extracted_clean.get('bcookie')),
                "lidc": bool(extracted_clean.get('lidc')),
            },
            "instructions": "Copia los valores en el formulario de configuración"
        }
    
    except Exception as e:
        logger.error(f"Error parseando cURL: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error parseando cURL: {str(e)}"
        }


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
        client = create_linkedin_client_with_cookies(
            config["li_at"],
            config["jsessionid"],
            bcookie=config.get("bcookie", ""),
            lidc=config.get("lidc", ""),
            user_match_history=config.get("user_match_history", ""),
            aam_uuid=config.get("aam_uuid", "")
        )
        
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
        if not os.path.exists(LOG_FILE):
            return "<pre>No logs yet</pre>"
        
        with open(LOG_FILE, "r") as f:
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
        if not os.path.exists(LOG_FILE):
            return {"logs": [], "total": 0}
        
        with open(LOG_FILE, "r") as f:
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


# ===== ENDPOINTS DE VALIDACIÓN Y PRUEBA =====
@app.post("/validate-cookies")
async def validate_cookies_endpoint(request: ValidateCookiesRequest):
    """
    Valida cookies contra LinkedIn.
    
    Endpoint separado de POST /admin para permitir validación bajo demanda
    sin invalidar las cookies (no hay múltiples IPs detectadas si el usuario
    cierra navegador antes de validar).
    
    Request JSON:
    {
        "li_at": "...",
        "jsessionid": "...",
        "bcookie": "...",
        "lidc": "...",
        "user_match_history": "...",
        "aam_uuid": "..."
    }
    
    Returns:
    {
        "success": true/false,
        "user_name": "Nombre Usuario" (si success=true),
        "detail": "error message" (si success=false)
    }
    """
    logger.info("=== ENDPOINT /validate-cookies - Validación bajo demanda ===")
    
    try:
        # Extraer valores del request
        li_at = request.li_at.strip()
        jsessionid = request.jsessionid.strip()
        bcookie = request.bcookie.strip()
        lidc = request.lidc.strip()
        user_match_history = request.user_match_history.strip()
        aam_uuid = request.aam_uuid.strip()
        
        # Validar requeridos
        if not li_at or not jsessionid:
            logger.warning("Validación sin cookies requeridas")
            return {
                "success": False,
                "detail": "li_at y jsessionid son requeridas"
            }
        
        logger.info(f"Validando cookies: li_at ({len(li_at)} chars), jsessionid ({len(jsessionid)} chars)")
        
        # Usar función de validación que retorna el perfil
        is_valid, validation_msg, profile_data = validate_linkedin_cookies_with_profile(
            li_at, jsessionid,
            bcookie=bcookie,
            lidc=lidc,
            user_match_history=user_match_history,
            aam_uuid=aam_uuid
        )
        
        if is_valid:
            logger.info("✓ Validación exitosa")
            user_name = profile_data.get('name', 'Unknown')
            updated_cookies = profile_data.get('updated_cookies', {})
            
            # 🔥 GUARDAR COOKIES ACTUALIZADAS
            if updated_cookies:
                logger.info("Guardando cookies actualizadas...")
                config = load_config()
                
                # Actualizar cookies en config
                for key, value in updated_cookies.items():
                    # Mapear nombres de cookies si es necesario
                    config_key = key.lower()
                    if config_key in config:
                        config[config_key] = value
                        logger.info(f"✓ Actualizado {config_key}")
                    elif key in config:
                        config[key] = value
                        logger.info(f"✓ Actualizado {key}")
                
                # Guardar config actualizado
                save_config(config)
                logger.info("✓ Cookies actualizadas guardadas en config.json")
            
            return {
                "success": True,
                "user_name": user_name,
                "detail": validation_msg,
                "cookies_updated": len(updated_cookies) > 0,
                "updated_fields": list(updated_cookies.keys())
            }
        else:
            logger.error(f"Validación fallida: {validation_msg}")
            return {
                "success": False,
                "detail": validation_msg
            }
            
    except Exception as e:
        logger.error(f"Error en /validate-cookies: {type(e).__name__}: {e}")
        return {
            "success": False,
            "detail": f"{type(e).__name__}: {str(e)[:200]}"
        }


@app.get("/messages")
async def get_messages():
    """
    Obtiene todos los mensajes/conversaciones de LinkedIn.
    
    **NOTA:** Esto es un endpoint de PRUEBA para verificar que la API funciona.
    Requiere cookies configuradas en /admin.
    
    Retorna:
    - conversations: Lista de conversaciones con metadatos
    - total: Total de conversaciones obtenidas
    - status: "success" o "error"
    """
    logger.info("=== ENDPOINT /messages - Obteniendo conversaciones ===")
    
    try:
        config = load_config()
        
        # Validar configuración
        if not config.get("li_at") or not config.get("jsessionid"):
            logger.warning("Cookies no configuradas")
            return {
                "status": "error",
                "detail": "Cookies no configuradas. Configúralas en /admin primero.",
                "conversations": [],
                "total": 0
            }
        
        logger.info("Creando cliente LinkedIn...")
        client = create_linkedin_client_with_cookies(
            config["li_at"],
            config["jsessionid"],
            bcookie=config.get("bcookie", ""),
            lidc=config.get("lidc", ""),
            user_match_history=config.get("user_match_history", ""),
            aam_uuid=config.get("aam_uuid", "")
        )
        
        logger.info("Obteniendo conversaciones...")
        conversations = client.get_conversations()
        
        if not conversations:
            logger.info("No hay conversaciones")
            return {
                "status": "success",
                "conversations": [],
                "total": 0,
                "message": "No hay conversaciones en LinkedIn"
            }
        
        logger.info(f"Encontradas {len(conversations)} conversaciones")
        
        # Procesar conversaciones
        result_conversations = []
        for conv in conversations[:10]:  # Límite de 10 para prueba
            try:
                conv_id = conv.get("conversation_urn_id") or conv.get("urn_id", "N/A")
                participants = conv.get("participants", [])
                participant_name = participants[0].get("name", "Unknown") if participants else "Unknown"
                subject = conv.get("subject", "Sin asunto")
                
                logger.info(f"Procesando conversación con {participant_name}")
                
                # Intentar obtener detalles
                try:
                    conv_details = client.get_conversation(conv_id)
                    elements = conv_details.get("elements", [])
                    
                    result_conversations.append({
                        "id": conv_id,
                        "participant": participant_name,
                        "subject": subject,
                        "message_count": len(elements),
                        "messages": [
                            {
                                "from": msg.get("from", {}).get("name", "Unknown"),
                                "body": msg.get("body", "")[:200],  # Primeros 200 chars
                                "timestamp": msg.get("createdAt")
                            }
                            for msg in elements[:5]  # Últimos 5 mensajes
                        ]
                    })
                except Exception as e:
                    logger.warning(f"No se pudo obtener detalles de conversación {conv_id}: {e}")
                    result_conversations.append({
                        "id": conv_id,
                        "participant": participant_name,
                        "subject": subject,
                        "error": str(e)
                    })
                    
            except Exception as e:
                logger.error(f"Error procesando conversación: {e}")
                continue
        
        logger.info(f"✓ Devolviendo {len(result_conversations)} conversaciones")
        
        return {
            "status": "success",
            "conversations": result_conversations,
            "total": len(conversations),
            "processed": len(result_conversations),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"✗ Error en /messages: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "status": "error",
            "detail": str(e),
            "error_type": type(e).__name__,
            "conversations": [],
            "total": 0
        }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Iniciando LinkedIn-n8n Gateway en http://localhost:8000")
    logger.info("Dashboard: http://localhost:8000/admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)
