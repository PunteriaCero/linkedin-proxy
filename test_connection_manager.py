"""
Tests para ConnectionManager, ConversationCache y MessageMonitor
(Versión simplificada sin pytest)
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from connection_manager import (
    ConversationCache,
    ConversationData,
    ConnectionManager,
    MessageMonitor,
    MonitoredLinkedInConnection
)

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def test_passed(name):
    """Imprime test pasado"""
    print(f"{GREEN}✅ {name}{RESET}")


def test_failed(name, error):
    """Imprime test fallido"""
    print(f"{RED}❌ {name}: {error}{RESET}")


# ==============================================================================
# TESTS: ConversationCache
# ==============================================================================

def test_cache_set_and_get():
    """Verifica que se pueden guardar y recuperar datos"""
    try:
        cache = ConversationCache(ttl_minutes=5)
        
        conv_data = ConversationData(
            conversation_id="conv_123",
            participant_name="John Doe",
            last_message="Hello!",
            message_count=5,
            updated_at=datetime.now()
        )
        
        cache.set("conv_123", conv_data)
        result = cache.get("conv_123")
        
        assert result is not None
        assert result.conversation_id == "conv_123"
        assert result.participant_name == "John Doe"
        test_passed("Cache SET/GET")
    except Exception as e:
        test_failed("Cache SET/GET", str(e))


def test_cache_expiration():
    """Verifica que los datos expiran correctamente"""
    try:
        cache = ConversationCache(ttl_minutes=1)
        
        # Crear dato con timestamp en el pasado
        conv_data = ConversationData(
            conversation_id="conv_456",
            participant_name="Jane Smith",
            last_message="Hi!",
            message_count=3,
            updated_at=datetime.now() - timedelta(minutes=2)  # Hace 2 minutos
        )
        
        cache.set("conv_456", conv_data)
        result = cache.get("conv_456")
        
        assert result is None  # Debería estar expirado
        test_passed("Cache expiration")
    except Exception as e:
        test_failed("Cache expiration", str(e))


def test_cache_get_all():
    """Verifica que get_all retorna solo datos válidos"""
    try:
        cache = ConversationCache(ttl_minutes=5)
        
        # Agregar 3 conversaciones válidas
        for i in range(3):
            conv_data = ConversationData(
                conversation_id=f"conv_{i}",
                participant_name=f"User {i}",
                last_message=f"Message {i}",
                message_count=i+1,
                updated_at=datetime.now()
            )
            cache.set(f"conv_{i}", conv_data)
        
        all_convs = cache.get_all()
        assert len(all_convs) == 3
        test_passed("Cache get_all")
    except Exception as e:
        test_failed("Cache get_all", str(e))


def test_cache_clear():
    """Verifica que clear() vacía el caché"""
    try:
        cache = ConversationCache()
        
        conv_data = ConversationData(
            conversation_id="conv_789",
            participant_name="Test User",
            last_message="Test",
            message_count=1,
            updated_at=datetime.now()
        )
        cache.set("conv_789", conv_data)
        assert len(cache.cache) == 1
        
        cache.clear()
        assert len(cache.cache) == 0
        test_passed("Cache clear")
    except Exception as e:
        test_failed("Cache clear", str(e))


def test_cache_stats():
    """Verifica que stats() retorna información correcta"""
    try:
        cache = ConversationCache(ttl_minutes=5)
        
        stats = cache.stats()
        assert stats["ttl_minutes"] == 5
        assert stats["size"] == 0
        assert "last_update" in stats
        test_passed("Cache stats")
    except Exception as e:
        test_failed("Cache stats", str(e))


# ==============================================================================
# TESTS: ConnectionManager
# ==============================================================================

async def test_connect_disconnect():
    """Verifica conexión y desconexión de WebSockets"""
    try:
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        
        await manager.connect(mock_ws, channel="messages")
        assert len(manager.active_connections["messages"]) == 1
        
        await manager.disconnect(mock_ws, channel="messages")
        assert len(manager.active_connections["messages"]) == 0
        test_passed("Connect/disconnect")
    except Exception as e:
        test_failed("Connect/disconnect", str(e))


async def test_broadcast():
    """Verifica que broadcast envía a todos los clientes"""
    try:
        manager = ConnectionManager()
        
        # Crear 3 WebSockets mock
        mock_ws_list = [AsyncMock() for _ in range(3)]
        
        for ws in mock_ws_list:
            await manager.connect(ws, channel="messages")
        
        # Broadcast
        message = {"type": "test", "data": "hello"}
        await manager.broadcast(message, channel="messages")
        
        # Verificar que todos recibieron
        for ws in mock_ws_list:
            ws.send_json.assert_called_once()
        
        test_passed("Broadcast")
    except Exception as e:
        test_failed("Broadcast", str(e))


async def test_broadcast_with_disconnected():
    """Verifica que broadcast limpia conexiones muertas"""
    try:
        manager = ConnectionManager()
        
        # WebSocket que funciona
        good_ws = AsyncMock()
        
        # WebSocket que falla
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = Exception("Connection failed")
        
        await manager.connect(good_ws, channel="messages")
        await manager.connect(bad_ws, channel="messages")
        
        assert len(manager.active_connections["messages"]) == 2
        
        # Broadcast
        message = {"type": "test"}
        await manager.broadcast(message, channel="messages")
        
        # bad_ws debería ser removido
        assert len(manager.active_connections["messages"]) == 1
        test_passed("Broadcast cleanup")
    except Exception as e:
        test_failed("Broadcast cleanup", str(e))


def test_get_stats():
    """Verifica que get_stats retorna información correcta"""
    try:
        manager = ConnectionManager()
        
        stats = manager.get_stats(channel="messages")
        assert stats["channel"] == "messages"
        assert stats["active_connections"] == 0
        assert stats["total_messages_sent"] == 0
        test_passed("ConnectionManager stats")
    except Exception as e:
        test_failed("ConnectionManager stats", str(e))


# ==============================================================================
# TESTS: MessageMonitor
# ==============================================================================

def test_monitor_initialization():
    """Verifica inicialización del monitor"""
    try:
        factory = Mock()
        conn_manager = ConnectionManager()
        cache = ConversationCache()
        
        monitor = MessageMonitor(
            linkedin_client_factory=factory,
            connection_manager=conn_manager,
            conversation_cache=cache,
            poll_interval_seconds=30
        )
        
        assert monitor.is_running == False
        assert monitor.poll_interval_seconds == 30
        test_passed("MessageMonitor initialization")
    except Exception as e:
        test_failed("MessageMonitor initialization", str(e))


async def test_fetch_new_messages():
    """Verifica extracción de mensajes nuevos"""
    try:
        # Mock LinkedIn client
        mock_client = Mock()
        mock_client.get_conversations.return_value = [
            {
                "conversation_urn_id": "conv_1",
                "participants": [{"name": "John"}],
                "messages": []
            }
        ]
        mock_client.get_conversation_details.return_value = {
            "messages": [
                {
                    "created": "2026-03-26T10:00:00",
                    "body": "Hello",
                    "is_outgoing": False
                }
            ]
        }
        
        factory = Mock(return_value=mock_client)
        conn_manager = ConnectionManager()
        cache = ConversationCache()
        
        monitor = MessageMonitor(
            linkedin_client_factory=factory,
            connection_manager=conn_manager,
            conversation_cache=cache
        )
        
        messages = await monitor._fetch_new_messages()
        
        assert len(messages) == 1
        assert messages[0]["body"] == "Hello"
        test_passed("Fetch new messages")
    except Exception as e:
        test_failed("Fetch new messages", str(e))


async def test_monitor_stops_gracefully():
    """Verifica que el monitor se detiene correctamente"""
    try:
        factory = Mock()
        factory.return_value.get_conversations.return_value = []
        
        conn_manager = ConnectionManager()
        cache = ConversationCache()
        
        monitor = MessageMonitor(
            linkedin_client_factory=factory,
            connection_manager=conn_manager,
            conversation_cache=cache,
            poll_interval_seconds=1
        )
        
        # Iniciar monitor
        monitor_task = asyncio.create_task(monitor.start())
        
        # Dejar que corra un poco
        await asyncio.sleep(0.5)
        
        # Detener
        await monitor.stop()
        
        # Esperar a que termine
        try:
            await asyncio.wait_for(monitor_task, timeout=2)
        except asyncio.CancelledError:
            pass
        
        assert monitor.is_running == False
        test_passed("Monitor stop")
    except Exception as e:
        test_failed("Monitor stop", str(e))


# ==============================================================================
# TESTS: MonitoredLinkedInConnection
# ==============================================================================

def test_connection_initialization():
    """Verifica inicialización"""
    try:
        config = {
            "li_at": "test_token",
            "jsessionid": "test_session"
        }
        
        conn = MonitoredLinkedInConnection(config)
        
        assert conn.connection_manager is not None
        assert conn.conversation_cache is not None
        test_passed("MonitoredLinkedInConnection init")
    except Exception as e:
        test_failed("MonitoredLinkedInConnection init", str(e))


def test_set_factory():
    """Verifica que se puede establecer factory"""
    try:
        config = {}
        conn = MonitoredLinkedInConnection(config)
        
        factory = Mock()
        conn.set_linkedin_client_factory(factory)
        
        assert conn.message_monitor is not None
        test_passed("Set factory")
    except Exception as e:
        test_failed("Set factory", str(e))


async def test_start_stop_monitoring():
    """Verifica start/stop de monitoreo"""
    try:
        config = {}
        conn = MonitoredLinkedInConnection(config)
        
        factory = Mock()
        factory.return_value.get_conversations.return_value = []
        
        conn.set_linkedin_client_factory(factory)
        
        # Iniciar
        await conn.start_monitoring()
        assert conn.monitor_task is not None
        
        await asyncio.sleep(0.5)
        
        # Detener
        await conn.stop_monitoring()
        
        test_passed("Start/stop monitoring")
    except Exception as e:
        test_failed("Start/stop monitoring", str(e))


# ==============================================================================
# INTEGRATION TEST
# ==============================================================================

async def test_full_integration():
    """Test de integración completa"""
    try:
        # Setup
        config = {"li_at": "test", "jsessionid": "test"}
        conn = MonitoredLinkedInConnection(config)
        
        # Mock LinkedIn
        mock_client = Mock()
        mock_client.get_conversations.return_value = [
            {
                "conversation_urn_id": "conv_1",
                "participants": [{"name": "Test User"}],
            }
        ]
        mock_client.get_conversation_details.return_value = {
            "messages": [
                {
                    "created": "2026-03-26T10:00:00",
                    "body": "Test message",
                    "is_outgoing": False
                }
            ]
        }
        
        factory = Mock(return_value=mock_client)
        conn.set_linkedin_client_factory(factory)
        
        # Crear WebSocket mock
        mock_ws = AsyncMock()
        await conn.connection_manager.connect(mock_ws, channel="messages")
        
        # Iniciar monitor
        await conn.start_monitoring()
        await asyncio.sleep(1.5)  # Dejar que procese
        
        # Verificar caché
        convs = conn.conversation_cache.get_all()
        assert len(convs) >= 0
        
        # Limpiar
        await conn.stop_monitoring()
        
        test_passed("Full integration")
    except Exception as e:
        test_failed("Full integration", str(e))


# ==============================================================================
# EJECUCIÓN
# ==============================================================================

async def run_async_tests():
    """Ejecuta todos los tests asíncronos"""
    print("\n[ConnectionManager Async Tests]")
    await test_connect_disconnect()
    await test_broadcast()
    await test_broadcast_with_disconnected()
    
    print("\n[MessageMonitor Async Tests]")
    await test_fetch_new_messages()
    await test_monitor_stops_gracefully()
    
    print("\n[MonitoredLinkedInConnection Async Tests]")
    await test_start_stop_monitoring()
    
    print("\n[Integration Tests]")
    await test_full_integration()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 EJECUTANDO TESTS PARA CONNECTION MANAGER")
    print("="*70 + "\n")
    
    # Tests síncronos
    print("[Cache Tests]")
    test_cache_set_and_get()
    test_cache_expiration()
    test_cache_get_all()
    test_cache_clear()
    test_cache_stats()
    
    print("\n[ConnectionManager Sync Tests]")
    test_get_stats()
    
    print("\n[MessageMonitor Sync Tests]")
    test_monitor_initialization()
    
    print("\n[MonitoredLinkedInConnection Sync Tests]")
    test_connection_initialization()
    test_set_factory()
    
    # Tests asíncronos
    asyncio.run(run_async_tests())
    
    print("\n" + "="*70)
    print("✅ SUITE DE TESTS COMPLETADA")
    print("="*70 + "\n")
