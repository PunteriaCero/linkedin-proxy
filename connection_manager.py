"""
LinkedIn Connection Manager
Mantiene conexiones estables con LinkedIn y notifica cambios en tiempo real.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Set, Dict, Optional, Any, Callable
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class ConversationData:
    """Datos de una conversación en caché"""
    conversation_id: str
    participant_name: str
    last_message: str
    message_count: int
    updated_at: datetime
    messages: list = None  # Últimos 10 mensajes
    
    def is_expired(self, ttl_minutes: int = 5) -> bool:
        """Verifica si el caché expiró"""
        return datetime.now() - self.updated_at > timedelta(minutes=ttl_minutes)


class ConversationCache:
    """Cache en-memory de conversaciones con TTL"""
    
    def __init__(self, ttl_minutes: int = 5):
        self.ttl_minutes = ttl_minutes
        self.cache: Dict[str, ConversationData] = {}
        self.last_update = datetime.now()
        logger.info(f"✓ ConversationCache inicializado (TTL: {ttl_minutes}min)")
    
    def set(self, conversation_id: str, data: ConversationData) -> None:
        """Almacena una conversación en caché"""
        self.cache[conversation_id] = data
        self.last_update = datetime.now()
        logger.debug(f"Cache SET: {conversation_id}")
    
    def get(self, conversation_id: str) -> Optional[ConversationData]:
        """Obtiene una conversación del caché (si no expiró)"""
        if conversation_id not in self.cache:
            return None
        
        data = self.cache[conversation_id]
        if data.is_expired(self.ttl_minutes):
            logger.debug(f"Cache EXPIRED: {conversation_id}")
            del self.cache[conversation_id]
            return None
        
        logger.debug(f"Cache HIT: {conversation_id}")
        return data
    
    def get_all(self) -> list:
        """Obtiene todas las conversaciones en caché (no expiradas)"""
        valid_conversations = []
        expired_keys = []
        
        for conv_id, data in self.cache.items():
            if data.is_expired(self.ttl_minutes):
                expired_keys.append(conv_id)
            else:
                valid_conversations.append(data)
        
        # Limpiar expirados
        for key in expired_keys:
            del self.cache[key]
        
        logger.debug(f"Cache SIZE: {len(valid_conversations)} conversaciones válidas")
        return valid_conversations
    
    def clear(self) -> None:
        """Limpia todo el caché"""
        self.cache.clear()
        logger.info("Cache limpiado")
    
    def stats(self) -> dict:
        """Retorna estadísticas del caché"""
        return {
            "size": len(self.cache),
            "last_update": self.last_update.isoformat(),
            "ttl_minutes": self.ttl_minutes
        }


class ConnectionManager:
    """Gestiona conexiones WebSocket para múltiples clientes"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.connection_metadata: Dict[WebSocket, dict] = {}
        logger.info("✓ ConnectionManager inicializado")
    
    async def connect(self, websocket: WebSocket, channel: str = "messages") -> None:
        """Acepta una nueva conexión WebSocket"""
        await websocket.accept()
        self.active_connections[channel].add(websocket)
        self.connection_metadata[websocket] = {
            "channel": channel,
            "connected_at": datetime.now(),
            "messages_received": 0
        }
        logger.info(f"✓ WebSocket conectado | channel={channel} | total={len(self.active_connections[channel])}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = "messages") -> None:
        """Desconecta un cliente WebSocket"""
        self.active_connections[channel].discard(websocket)
        if websocket in self.connection_metadata:
            meta = self.connection_metadata.pop(websocket)
            logger.info(f"✓ WebSocket desconectado | channel={channel} | messages_received={meta['messages_received']}")
    
    async def broadcast(self, message: Dict[str, Any], channel: str = "messages") -> None:
        """Envía un mensaje a todos los clientes en el canal"""
        if channel not in self.active_connections or not self.active_connections[channel]:
            logger.debug(f"No hay clientes conectados en {channel}")
            return
        
        disconnected = set()
        payload = json.dumps(message)
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["messages_received"] += 1
            except Exception as e:
                logger.warning(f"Error enviando mensaje a cliente: {e}")
                disconnected.add(connection)
        
        # Limpiar conexiones muertas
        for conn in disconnected:
            await self.disconnect(conn, channel)
        
        logger.debug(f"Broadcast enviado | channel={channel} | recipients={len(self.active_connections[channel])}")
    
    def get_stats(self, channel: str = "messages") -> dict:
        """Retorna estadísticas de conexiones"""
        connections = self.active_connections.get(channel, set())
        total_messages = sum(
            m.get("messages_received", 0) 
            for m in self.connection_metadata.values() 
            if m.get("channel") == channel
        )
        return {
            "channel": channel,
            "active_connections": len(connections),
            "total_messages_sent": total_messages,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_connection_details(self) -> list:
        """Retorna detalles de todas las conexiones"""
        details = []
        for ws, meta in self.connection_metadata.items():
            uptime = (datetime.now() - meta["connected_at"]).total_seconds()
            details.append({
                "channel": meta["channel"],
                "uptime_seconds": uptime,
                "messages_received": meta["messages_received"],
                "connected_at": meta["connected_at"].isoformat()
            })
        return details


class MessageMonitor:
    """Monitor de mensajes con reconexión automática y heartbeat"""
    
    def __init__(
        self,
        linkedin_client_factory: Callable,
        connection_manager: ConnectionManager,
        conversation_cache: ConversationCache,
        poll_interval_seconds: int = 30,
        max_retries: int = 5
    ):
        self.linkedin_client_factory = linkedin_client_factory
        self.connection_manager = connection_manager
        self.conversation_cache = conversation_cache
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries
        self.is_running = False
        self.last_sync_time = datetime.now()
        self.error_count = 0
        self.processed_message_ids = set()
        logger.info(f"✓ MessageMonitor inicializado | poll_interval={poll_interval_seconds}s")
    
    async def start(self) -> None:
        """Inicia el monitor de mensajes"""
        self.is_running = True
        logger.info("🚀 Iniciando MessageMonitor...")
        await self._monitor_loop()
    
    async def stop(self) -> None:
        """Detiene el monitor"""
        self.is_running = False
        logger.info("⏹️ Deteniendo MessageMonitor...")
    
    async def _monitor_loop(self) -> None:
        """Loop principal de monitoreo"""
        retry_count = 0
        
        while self.is_running:
            try:
                logger.debug(f"[Monitor] Ciclo de sincronización #{retry_count + 1}")
                
                # Obtener mensajes nuevos
                new_messages = await self._fetch_new_messages()
                
                if new_messages:
                    logger.info(f"[Monitor] {len(new_messages)} mensajes nuevos detectados")
                    
                    # Broadcast a todos los clientes WebSocket
                    for msg in new_messages:
                        await self.connection_manager.broadcast({
                            "type": "new_message",
                            "data": msg,
                            "timestamp": datetime.now().isoformat()
                        })
                
                # Reset contador de errores si fue exitoso
                retry_count = 0
                self.error_count = 0
                
                # Esperar antes del siguiente ciclo
                await asyncio.sleep(self.poll_interval_seconds)
                
            except Exception as e:
                retry_count += 1
                self.error_count += 1
                
                if retry_count > self.max_retries:
                    logger.error(f"[Monitor] Max retries alcanzado ({self.max_retries}). Esperando antes de reintentar...")
                    retry_count = 0
                    await asyncio.sleep(60)  # Esperar 1 minuto completo
                else:
                    wait_time = min(2 ** retry_count, 30)  # Exponential backoff max 30s
                    logger.warning(f"[Monitor] Error: {e}. Reintentando en {wait_time}s...")
                    await asyncio.sleep(wait_time)
    
    async def _fetch_new_messages(self) -> list:
        """Obtiene mensajes nuevos desde LinkedIn"""
        try:
            client = self.linkedin_client_factory()
            conversations = client.get_conversations()
            
            new_messages = []
            
            for conv in conversations:
                conv_id = conv.get("conversation_urn_id") or conv.get("urn_id")
                participants = conv.get("participants", [])
                participant_name = participants[0].get("name", "Unknown") if participants else "Unknown"
                
                if not conv_id:
                    continue
                
                try:
                    # Obtener detalles de la conversación
                    details = client.get_conversation_details(conv_id)
                    messages = details.get("messages", [])
                    
                    for msg in messages:
                        msg_timestamp = msg.get("created", str(int(time.time())))
                        msg_id = f"{conv_id}_{msg_timestamp}"
                        
                        # Detectar si es nuevo
                        if msg_id not in self.processed_message_ids:
                            new_messages.append({
                                "conversation_id": conv_id,
                                "message_id": msg_id,
                                "participant_name": participant_name,
                                "body": msg.get("body", ""),
                                "created_at": msg_timestamp,
                                "is_outgoing": msg.get("is_outgoing", False)
                            })
                            self.processed_message_ids.add(msg_id)
                    
                    # Actualizar caché
                    self.conversation_cache.set(conv_id, ConversationData(
                        conversation_id=conv_id,
                        participant_name=participant_name,
                        last_message=messages[0].get("body", "") if messages else "Sin mensajes",
                        message_count=len(messages),
                        updated_at=datetime.now(),
                        messages=messages[:10]
                    ))
                    
                except Exception as e:
                    logger.warning(f"Error obteniendo detalles de {conv_id}: {e}")
                    continue
            
            self.last_sync_time = datetime.now()
            return new_messages
        
        except Exception as e:
            logger.error(f"Error en _fetch_new_messages: {e}")
            raise
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del monitor"""
        return {
            "is_running": self.is_running,
            "last_sync": self.last_sync_time.isoformat(),
            "error_count": self.error_count,
            "processed_messages": len(self.processed_message_ids),
            "poll_interval_seconds": self.poll_interval_seconds,
            "connection_stats": self.connection_manager.get_stats(),
            "cache_stats": self.conversation_cache.stats()
        }


class MonitoredLinkedInConnection:
    """Wrapper que combina monitor + cache + websocket"""
    
    def __init__(self, config: dict):
        self.config = config
        self.connection_manager = ConnectionManager()
        self.conversation_cache = ConversationCache(ttl_minutes=5)
        self.message_monitor: Optional[MessageMonitor] = None
        self.monitor_task: Optional[asyncio.Task] = None
        logger.info("✓ MonitoredLinkedInConnection inicializado")
    
    def set_linkedin_client_factory(self, factory: Callable) -> None:
        """Define la factory para crear clientes LinkedIn"""
        self.message_monitor = MessageMonitor(
            linkedin_client_factory=factory,
            connection_manager=self.connection_manager,
            conversation_cache=self.conversation_cache,
            poll_interval_seconds=30  # Configurar según necesidad
        )
    
    async def start_monitoring(self) -> None:
        """Inicia el monitoreo en background"""
        if self.message_monitor:
            self.monitor_task = asyncio.create_task(self.message_monitor.start())
            logger.info("✓ Background monitoring iniciado")
    
    async def stop_monitoring(self) -> None:
        """Detiene el monitoreo"""
        if self.message_monitor:
            await self.message_monitor.stop()
        
        if self.monitor_task:
            try:
                await asyncio.wait_for(self.monitor_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Monitor task no se detuvo en 5s, cancelando...")
                self.monitor_task.cancel()
            logger.info("✓ Background monitoring detenido")
    
    def get_comprehensive_stats(self) -> dict:
        """Retorna estadísticas completas del sistema"""
        return {
            "monitor": self.message_monitor.get_stats() if self.message_monitor else None,
            "connections": self.connection_manager.get_connection_details(),
            "cache": self.conversation_cache.stats()
        }
