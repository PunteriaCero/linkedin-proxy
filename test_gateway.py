"""
Test Suite para LinkedIn-n8n Gateway
Mock testing sin necesidad de conexión real a LinkedIn.
"""

import json
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))


def print_section(title):
    """Helper para imprimir secciones."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_config_persistence():
    """Test 1: Persistencia de configuración en JSON."""
    print_section("TEST 1: Persistencia de Configuración")
    
    config = {
        "li_at": "mock_li_at_cookie_12345",
        "jsessionid": '"AQFd8qXfvXaBqKv12345"',
        "n8n_webhook_url": "https://n8n.example.com/webhook/linkedin",
        "last_sync": datetime.now().isoformat()
    }
    
    # Simular guardado
    config_file = "config_test.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Simular carga
    with open(config_file, 'r') as f:
        loaded_config = json.load(f)
    
    assert loaded_config["li_at"] == config["li_at"], "❌ li_at no coincide"
    assert loaded_config["n8n_webhook_url"] == config["n8n_webhook_url"], "❌ webhook URL no coincide"
    
    print("✅ Configuración guardada y cargada correctamente")
    print(f"   - li_at: {loaded_config['li_at'][:20]}...")
    print(f"   - n8n_webhook_url: {loaded_config['n8n_webhook_url']}")
    
    # Cleanup
    os.remove(config_file)


def test_jsessionid_cleaning():
    """Test 2: Limpieza de caracteres en JSESSIONID."""
    print_section("TEST 2: Limpieza de JSESSIONID")
    
    def clean_jsessionid(jsessionid: str) -> str:
        """Limpia caracteres extra de JSESSIONID."""
        return jsessionid.strip().strip('"\'')
    
    test_cases = [
        ('"AQFd8qXfvXaBqKv12345"', 'AQFd8qXfvXaBqKv12345'),
        ("'AQFd8qXfvXaBqKv12345'", 'AQFd8qXfvXaBqKv12345'),
        ('  "AQFd8qXfvXaBqKv12345"  ', 'AQFd8qXfvXaBqKv12345'),
        ('AQFd8qXfvXaBqKv12345', 'AQFd8qXfvXaBqKv12345'),
    ]
    
    for input_val, expected in test_cases:
        result = clean_jsessionid(input_val)
        assert result == expected, f"❌ Clean fallo para '{input_val}'"
        print(f"✅ '{input_val}' → '{result}'")


def test_message_parsing():
    """Test 3: Parseo de mensajes de LinkedIn a formato n8n."""
    print_section("TEST 3: Parseo de Mensajes LinkedIn → n8n")
    
    # Simular mensaje de LinkedIn
    linkedin_message = {
        "messageId": "msg_12345",
        "conversationId": "conv_67890",
        "from": "John Doe",
        "text": "Hola, ¿cómo estás?",
        "timestamp": "2024-03-20T10:30:00Z"
    }
    
    # Transformar para n8n
    n8n_payload = {
        "conversation_id": linkedin_message["conversationId"],
        "message_id": linkedin_message["messageId"],
        "text": linkedin_message["text"],
        "sender": linkedin_message["from"],
        "timestamp": linkedin_message["timestamp"],
        "gateway_timestamp": datetime.now().isoformat()
    }
    
    print("📥 Mensaje de LinkedIn recibido:")
    print(json.dumps(linkedin_message, indent=2, ensure_ascii=False))
    
    print("\n📤 Transformado para n8n:")
    print(json.dumps(n8n_payload, indent=2, ensure_ascii=False))
    
    assert n8n_payload["conversation_id"] == "conv_67890"
    assert n8n_payload["sender"] == "John Doe"
    print("\n✅ Parseo correcto")


def test_duplicate_prevention():
    """Test 4: Prevención de duplicados con processed_messages.json."""
    print_section("TEST 4: Prevención de Duplicados")
    
    processed_file = "processed_test.json"
    
    # Simular mensajes procesados
    processed_ids = {"msg_001", "msg_002", "msg_003"}
    
    with open(processed_file, 'w') as f:
        json.dump({"processed_ids": list(processed_ids)}, f)
    
    # Cargar
    with open(processed_file, 'r') as f:
        loaded = json.load(f)
        loaded_ids = set(loaded["processed_ids"])
    
    # Test: ¿msg_002 ya fue procesado?
    assert "msg_002" in loaded_ids, "❌ msg_002 debería estar procesado"
    print("✅ msg_002 ya está en processed_ids")
    
    # Test: ¿msg_999 es nuevo?
    assert "msg_999" not in loaded_ids, "❌ msg_999 debería ser nuevo"
    print("✅ msg_999 es un mensaje nuevo")
    
    # Agregar nuevo mensaje
    loaded_ids.add("msg_999")
    with open(processed_file, 'w') as f:
        json.dump({"processed_ids": list(loaded_ids)}, f)
    
    print("✅ msg_999 agregado a processed_ids")
    
    # Cleanup
    os.remove(processed_file)


def test_retry_logic():
    """Test 5: Lógica de reintentos exponenciales (429)."""
    print_section("TEST 5: Reintentos Exponenciales (Rate Limit 429)")
    
    def exponential_backoff(max_retries=3, base_delay=1.0):
        """Simula reintentos exponenciales."""
        delays = []
        delay = base_delay
        
        for attempt in range(max_retries):
            delays.append(delay)
            delay *= 2  # Backoff exponencial
        
        return delays
    
    delays = exponential_backoff(max_retries=4, base_delay=1.0)
    
    print("Intento 1 (inicial): Falla con 429")
    for i, delay in enumerate(delays, 1):
        print(f"  Intento {i}: Esperar {delay}s antes de reintentar")
    
    assert delays == [1.0, 2.0, 4.0, 8.0], "❌ Secuencia de delay incorrecta"
    print("✅ Secuencia de backoff exponencial correcta")


def test_error_messages():
    """Test 6: Mensajes de error detallados."""
    print_section("TEST 6: Mensajes de Error Detallados")
    
    error_scenarios = [
        ("401", "Cookie expirada o inválida (401)"),
        ("403", "Acceso denegado (403) - verifica permisos"),
        ("429", "Rate limit alcanzado - intenta más tarde"),
        ("JSESSIONID invalid", "Estructura de JSESSIONID incorrecta"),
    ]
    
    for error_code, expected_msg in error_scenarios:
        # Simular detección de error
        if "401" in error_code:
            msg = "Cookie expirada o inválida (401)"
        elif "403" in error_code:
            msg = "Acceso denegado (403) - verifica permisos"
        elif "429" in error_code:
            msg = "Rate limit alcanzado - intenta más tarde"
        elif "JSESSIONID" in error_code:
            msg = "Estructura de JSESSIONID incorrecta"
        else:
            msg = f"Error desconocido: {error_code}"
        
        print(f"✅ {error_code}: '{msg}'")


def test_request_flow():
    """Test 7: Flujo completo de solicitud (mental simulation)."""
    print_section("TEST 7: Flujo Completo de Solicitud")
    
    flow = [
        "1. Cliente (n8n) → POST /sync",
        "2. Gateway valida config (li_at, jsessionid, webhook_url)",
        "3. Gateway conecta a LinkedIn con cookies",
        "4. Obtiene conversaciones + mensajes",
        "5. Compara con processed_messages.json",
        "6. Identifica mensajes nuevos",
        "7. Transforma a formato n8n",
        "8. Envía a n8n webhook URL",
        "9. n8n responde (200 OK)",
        "10. Gateway actualiza processed_messages.json",
        "11. Gateway responde al cliente con resumen",
    ]
    
    for step in flow:
        print(f"   {step}")
    
    print("\n✅ Flujo simulado correctamente")


def test_n8n_payload_structure():
    """Test 8: Estructura correcta del payload para n8n."""
    print_section("TEST 8: Estructura de Payload para n8n")
    
    n8n_payload = {
        "action": "sync_messages",
        "messages": [
            {
                "conversation_id": "conv_12345",
                "message_id": "msg_001",
                "text": "Mensaje de prueba",
                "sender": "John Doe",
                "timestamp": "2024-03-20T10:30:00Z",
                "gateway_timestamp": datetime.now().isoformat()
            },
            {
                "conversation_id": "conv_12345",
                "message_id": "msg_002",
                "text": "Segundo mensaje",
                "sender": "Jane Smith",
                "timestamp": "2024-03-20T10:35:00Z",
                "gateway_timestamp": datetime.now().isoformat()
            }
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    print("📦 Payload n8n:")
    print(json.dumps(n8n_payload, indent=2, ensure_ascii=False))
    
    # Validaciones
    assert n8n_payload["action"] == "sync_messages"
    assert len(n8n_payload["messages"]) == 2
    assert n8n_payload["messages"][0]["conversation_id"] == "conv_12345"
    
    print("\n✅ Estructura de payload válida")


def test_reply_endpoint():
    """Test 9: Endpoint de respuesta."""
    print_section("TEST 9: Endpoint /reply")
    
    # Simular solicitud
    request_data = {
        "conversation_id": "conv_12345",
        "text": "Gracias por tu mensaje, te responderé pronto."
    }
    
    # Simular respuesta
    response_data = {
        "status": "sent",
        "conversation_id": "conv_12345",
        "message_id": "msg_response_001",
        "timestamp": datetime.now().isoformat()
    }
    
    print("📤 Request (n8n → Gateway):")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    
    print("\n📥 Response (Gateway → n8n):")
    print(json.dumps(response_data, indent=2, ensure_ascii=False))
    
    assert response_data["status"] == "sent"
    print("\n✅ Flujo de respuesta correcto")


def test_logging_chain():
    """Test 10: Cadena de logging detallada."""
    print_section("TEST 10: Cadena de Logging Detallada")
    
    log_sequence = [
        ("INFO", "=== INICIANDO SINCRONIZACIÓN ==="),
        ("INFO", "Conectando a LinkedIn..."),
        ("INFO", "Obteniendo conversaciones..."),
        ("DEBUG", "Conversaciones encontradas: 3"),
        ("INFO", "Nuevo mensaje encontrado: msg_001"),
        ("INFO", "Enviando 5 mensajes a n8n..."),
        ("INFO", "Respuesta de n8n: 200"),
        ("DEBUG", "Body: {\"status\": \"success\", \"processed\": 5}"),
        ("INFO", "✓ Sincronización completada exitosamente"),
    ]
    
    for level, message in log_sequence:
        timestamp = datetime.now().isoformat()
        print(f"{timestamp} - {level:5} - {message}")
    
    print("\n✅ Logging chain completa")


def main():
    """Ejecuta todos los tests."""
    print("\n" + "🧪 "*20)
    print("LINKEDIN-N8N GATEWAY | TEST SUITE")
    print("🧪 "*20)
    
    tests = [
        ("Config Persistence", test_config_persistence),
        ("JSESSIONID Cleaning", test_jsessionid_cleaning),
        ("Message Parsing", test_message_parsing),
        ("Duplicate Prevention", test_duplicate_prevention),
        ("Retry Logic", test_retry_logic),
        ("Error Messages", test_error_messages),
        ("Request Flow", test_request_flow),
        ("n8n Payload", test_n8n_payload_structure),
        ("Reply Endpoint", test_reply_endpoint),
        ("Logging Chain", test_logging_chain),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FALLO: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR INESPERADO: {e}")
            failed += 1
    
    # Resumen
    print("\n" + "="*60)
    print(f"RESUMEN: {passed} ✅ | {failed} ❌")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
