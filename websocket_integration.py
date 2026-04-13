"""
Integración de WebSocket al main.py existente
Este archivo debe ser importado en main.py después de crear la app FastAPI
"""

from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
import logging

# Importar los managers
from connection_manager import (
    MonitoredLinkedInConnection,
    ConversationCache,
    ConnectionManager
)

logger = logging.getLogger(__name__)

# Variable global para el monitored connection
monitored_connection: Optional[MonitoredLinkedInConnection] = None


def setup_websocket_lifespan(app, load_config, create_linkedin_client_with_cookies):
    """
    Configura el lifespan de FastAPI para iniciar/detener el monitoreo.
    
    Llamar así en main.py, JUSTO DESPUÉS de crear la app:
    
    ```python
    app = FastAPI(...)
    setup_websocket_lifespan(app, load_config, create_linkedin_client_with_cookies)
    ```
    """
    global monitored_connection
    
    @asynccontextmanager
    async def lifespan(fastapi_app):
        """Lifespan de FastAPI"""
        logger.info("🚀 STARTUP - Inicializando WebSocket monitoring")
        
        # Inicializar monitored connection
        config = load_config()
        monitored_connection = MonitoredLinkedInConnection(config)
        
        # Factory para crear clientes LinkedIn
        def linkedin_client_factory():
            config = load_config()
            return create_linkedin_client_with_cookies(
                config["li_at"],
                config["jsessionid"],
                bcookie=config.get("bcookie", ""),
                lidc=config.get("lidc", ""),
                user_match_history=config.get("user_match_history", ""),
                aam_uuid=config.get("aam_uuid", "")
            )
        
        # Solo iniciar si hay cookies configuradas
        if config.get("li_at") and config.get("jsessionid"):
            monitored_connection.set_linkedin_client_factory(linkedin_client_factory)
            try:
                await monitored_connection.start_monitoring()
                logger.info("✓ Monitoreo de LinkedIn iniciado")
            except Exception as e:
                logger.error(f"Error iniciando monitoreo: {e}")
        else:
            logger.warning("⚠️ Cookies no configuradas - monitoreo deshabilitado")
        
        yield  # App corre aquí
        
        logger.info("🛑 SHUTDOWN - Deteniendo WebSocket monitoring")
        
        # Limpiar
        if monitored_connection:
            await monitored_connection.stop_monitoring()
            logger.info("✓ Monitoreo de LinkedIn detenido")
    
    # Aplicar el lifespan a la app
    app.router.lifespan_context = lifespan
    logger.info("✓ WebSocket lifespan configurado")


def setup_websocket_endpoints(app, load_config):
    """
    Configura los endpoints WebSocket.
    
    Llamar así en main.py, DESPUÉS de setup_websocket_lifespan:
    
    ```python
    setup_websocket_endpoints(app, load_config)
    ```
    """
    global monitored_connection
    
    # ==============================================================================
    # NUEVOS ENDPOINTS
    # ==============================================================================
    
    @app.websocket("/ws/messages")
    async def websocket_messages(websocket: WebSocket):
        """
        WebSocket endpoint para recibir mensajes en tiempo real.
        
        Uso desde JavaScript:
        ```
        const ws = new WebSocket("ws://localhost:8000/ws/messages");
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Mensaje:", data);
        };
        ws.send(JSON.stringify({type: "ping"}));
        ```
        
        Ejemplos de mensajes que recibirás:
        - {"type": "new_message", "data": {...}, "timestamp": "..."}
        - {"type": "connection_status", "status": "connected", "timestamp": "..."}
        - {"type": "pong", "timestamp": "..."}
        """
        if not monitored_connection:
            await websocket.close(code=1000, reason="Monitor no disponible")
            logger.warning("WebSocket cerrado: Monitor no disponible")
            return
        
        try:
            # Conectar
            await monitored_connection.connection_manager.connect(websocket, channel="messages")
            logger.info(f"✓ Cliente WebSocket conectado")
            
            # Enviar estado inicial
            await websocket.send_json({
                "type": "connection_status",
                "status": "connected",
                "message": "Conectado al monitor de LinkedIn",
                "timestamp": datetime.now().isoformat()
            })
            
            # Mantener conexión abierta
            while True:
                data = await websocket.receive_text()
                
                # Responder a ping
                if data.lower().strip() == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
        
        except WebSocketDisconnect:
            await monitored_connection.connection_manager.disconnect(websocket, channel="messages")
            logger.info("✓ Cliente WebSocket desconectado")
        
        except Exception as e:
            logger.error(f"Error en WebSocket: {e}")
            try:
                await websocket.close(code=1011, reason=str(e))
            except:
                pass
    
    
    @app.get("/conversations")
    async def get_conversations_cached():
        """
        Obtiene conversaciones desde el caché (actualizado en tiempo real).
        
        Respuesta:
        ```json
        {
            "status": "success",
            "conversations": [
                {
                    "id": "conv_123",
                    "participant": "John Doe",
                    "last_message": "Hello world...",
                    "message_count": 5,
                    "updated_at": "2026-03-26T10:30:00..."
                }
            ],
            "cache_info": {
                "size": 5,
                "last_update": "...",
                "ttl_minutes": 5
            },
            "monitor_stats": {...}
        }
        ```
        """
        from fastapi import HTTPException
        
        if not monitored_connection:
            raise HTTPException(status_code=503, detail="Monitor no disponible")
        
        try:
            conversations = monitored_connection.conversation_cache.get_all()
            
            return {
                "status": "success",
                "conversations": [
                    {
                        "id": conv.conversation_id,
                        "participant": conv.participant_name,
                        "last_message": conv.last_message[:100],
                        "message_count": conv.message_count,
                        "updated_at": conv.updated_at.isoformat()
                    }
                    for conv in conversations
                ],
                "cache_info": monitored_connection.conversation_cache.stats(),
                "monitor_stats": monitored_connection.message_monitor.get_stats() if monitored_connection.message_monitor else None,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error en get_conversations: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/conversations/{conversation_id}/messages")
    async def get_conversation_messages(conversation_id: str):
        """
        Obtiene el historial de mensajes de una conversación (desde caché).
        
        Parámetros:
        - conversation_id: ID de la conversación (obtenible desde /conversations)
        
        Respuesta:
        ```json
        {
            "status": "success",
            "conversation_id": "conv_123",
            "participant": "John Doe",
            "message_count": 5,
            "messages": [...],
            "updated_at": "...",
            "timestamp": "..."
        }
        ```
        """
        from fastapi import HTTPException
        
        if not monitored_connection:
            raise HTTPException(status_code=503, detail="Monitor no disponible")
        
        try:
            conv_data = monitored_connection.conversation_cache.get(conversation_id)
            
            if not conv_data:
                raise HTTPException(status_code=404, detail="Conversación no encontrada en caché")
            
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "participant": conv_data.participant_name,
                "message_count": conv_data.message_count,
                "messages": conv_data.messages or [],
                "updated_at": conv_data.updated_at.isoformat(),
                "timestamp": datetime.now().isoformat()
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error obteniendo mensajes: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/monitor/stats")
    async def get_monitor_stats():
        """
        Obtiene estadísticas detalladas del monitor.
        
        Retorna información sobre:
        - Si el monitor está corriendo
        - Número de conexiones WebSocket activas
        - Tamaño del caché
        - Contador de errores
        - Timestamp de última sincronización
        
        Respuesta:
        ```json
        {
            "status": "success",
            "stats": {
                "monitor": {...},
                "connections": [...],
                "cache": {...}
            }
        }
        ```
        """
        from fastapi import HTTPException
        
        if not monitored_connection:
            raise HTTPException(status_code=503, detail="Monitor no disponible")
        
        try:
            return {
                "status": "success",
                "stats": monitored_connection.get_comprehensive_stats(),
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/monitor/restart")
    async def restart_monitor():
        """
        Reinicia el monitor de mensajes.
        
        Útil para:
        - Recuperarse de errores
        - Actualizar configuración de cookies
        - Resetear el caché
        
        Requiere que las cookies estén configuradas en /admin.
        """
        from fastapi import HTTPException
        
        try:
            config = load_config()
            
            if not config.get("li_at") or not config.get("jsessionid"):
                raise HTTPException(status_code=400, detail="Cookies no configuradas")
            
            # Detener monitor actual
            if monitored_connection:
                await monitored_connection.stop_monitoring()
            
            # Reinicializar
            from connection_manager import MonitoredLinkedInConnection
            from main import create_linkedin_client_with_cookies
            
            monitored_connection = MonitoredLinkedInConnection(config)
            
            def linkedin_client_factory():
                config = load_config()
                return create_linkedin_client_with_cookies(
                    config["li_at"],
                    config["jsessionid"],
                    bcookie=config.get("bcookie", ""),
                    lidc=config.get("lidc", ""),
                    user_match_history=config.get("user_match_history", ""),
                    aam_uuid=config.get("aam_uuid", "")
                )
            
            monitored_connection.set_linkedin_client_factory(linkedin_client_factory)
            await monitored_connection.start_monitoring()
            
            logger.info("✓ Monitor reiniciado")
            
            return {
                "status": "success",
                "message": "Monitor reiniciado exitosamente",
                "timestamp": datetime.now().isoformat()
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error reiniciando monitor: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    logger.info("✓ WebSocket endpoints configurados")
