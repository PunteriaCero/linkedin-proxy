"""
Extensiones de WebSocket para main.py
Agregar estos imports y funciones al main.py existente
"""

# ==============================================================================
# AGREGAR ESTOS IMPORTS AL TOP DE main.py
# ==============================================================================

from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from connection_manager import (
    MonitoredLinkedInConnection,
    ConversationCache,
    ConnectionManager
)

# ==============================================================================
# VARIABLE GLOBAL (después de crear la app)
# ==============================================================================

# Monitor global para la conexión con LinkedIn
monitored_connection: Optional[MonitoredLinkedInConnection] = None


# ==============================================================================
# LIFESPAN EVENTS (reemplazar FastAPI(app) con esto)
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events para FastAPI.
    Inicia el monitor al startup y lo detiene al shutdown.
    """
    global monitored_connection
    
    logger.info("🚀 FastAPI STARTUP")
    
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
    
    logger.info("🛑 FastAPI SHUTDOWN")
    
    # Limpiar
    if monitored_connection:
        await monitored_connection.stop_monitoring()
        logger.info("✓ Monitoreo de LinkedIn detenido")


# Actualizar la definición de FastAPI:
# app = FastAPI(lifespan=lifespan, ...)


# ==============================================================================
# NUEVOS ENDPOINTS
# ==============================================================================

@app.websocket("/ws/messages")
async def websocket_messages(websocket: WebSocket):
    """
    WebSocket endpoint para recibir mensajes en tiempo real.
    
    Uso:
    ```
    ws = new WebSocket("ws://localhost:8000/ws/messages");
    ws.onmessage = (event) => {
        console.log("Mensaje:", JSON.parse(event.data));
    };
    ```
    
    Ejemplos de mensajes:
    - {"type": "new_message", "data": {...}, "timestamp": "..."}
    - {"type": "connection_status", "status": "connected", "timestamp": "..."}
    """
    global monitored_connection
    
    if not monitored_connection:
        await websocket.close(code=1000, reason="Monitor no disponible")
        return
    
    try:
        # Conectar
        await monitored_connection.connection_manager.connect(websocket, channel="messages")
        
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
            # Echo del cliente para heartbeat/keepalive
            if data.lower() == "ping":
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
    
    Retorna:
    - conversations: Lista de conversaciones con últimos mensajes
    - cache_info: Información del caché (size, última actualización)
    - monitor_stats: Estadísticas del monitor
    """
    global monitored_connection
    
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
    - conversation_id: ID de la conversación (de /conversations)
    
    Retorna:
    - messages: Últimos 10 mensajes de la conversación
    - participant: Nombre del participante
    - message_count: Total de mensajes
    """
    global monitored_connection
    
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
    
    Retorna:
    - monitor_running: Si el monitor está activo
    - active_connections: Número de clientes WebSocket conectados
    - cache_size: Conversaciones en caché
    - error_count: Errores desde último reinicio
    - last_sync: Timestamp de última sincronización
    """
    global monitored_connection
    
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
    Útil para recuperarse de errores o actualizar configuración.
    
    Requiere que las cookies estén configuradas.
    """
    global monitored_connection
    
    try:
        config = load_config()
        
        if not config.get("li_at") or not config.get("jsessionid"):
            raise HTTPException(status_code=400, detail="Cookies no configuradas")
        
        # Detener monitor actual
        if monitored_connection:
            await monitored_connection.stop_monitoring()
        
        # Reinicializar
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


# ==============================================================================
# CAMBIOS EN OTROS ENDPOINTS
# ==============================================================================

# En POST /admin, después de guardar config, reiniciar el monitor:
# if monitored_connection:
#     await monitored_connection.stop_monitoring()
# 
# # Reiniciar con nueva config
# monitored_connection = MonitoredLinkedInConnection(config)
# monitored_connection.set_linkedin_client_factory(linkedin_client_factory)
# await monitored_connection.start_monitoring()
