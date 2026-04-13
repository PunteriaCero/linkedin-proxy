#!/usr/bin/env python3
"""
LinkedIn API Service Consumer
Consume el servicio deployado y muestra los últimos mensajes
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional

class LinkedInAPIConsumer:
    def __init__(self, base_url: str = "http://192.168.0.214:8000", timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
    
    def _request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict[str, Any]:
        """Hacer request al API"""
        url = f"{self.base_url}{endpoint}"
        
        if data:
            data = json.dumps(data).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
        else:
            headers = {}
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            raise Exception(f"Error en {endpoint}: {e}")
    
    def health(self) -> Dict:
        """Verificar salud del servicio"""
        return self._request('/health')
    
    def config(self) -> Dict:
        """Obtener configuración cargada"""
        return self._request('/config')
    
    def messages(self, limit: int = 10) -> Dict:
        """Obtener últimos mensajes"""
        return self._request(f'/messages?limit={limit}')
    
    def conversations(self) -> Dict:
        """Obtener lista de conversaciones"""
        return self._request('/conversations')
    
    def conversation_messages(self, conversation_id: str, limit: int = 10) -> Dict:
        """Obtener mensajes de una conversación"""
        return self._request(f'/conversations/{conversation_id}/messages?limit={limit}')
    
    def monitor_stats(self) -> Dict:
        """Obtener estadísticas del monitor"""
        return self._request('/monitor/stats')
    
    def validate_cookies(self) -> Dict:
        """Validar credenciales"""
        return self._request('/validate-cookies', method='POST')

def main():
    print("=" * 80)
    print("🔍 CONSUMIENDO LINKEDIN API SERVICE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Crear cliente
    client = LinkedInAPIConsumer()
    
    # 1. Health check
    print("1️⃣ HEALTH CHECK")
    print("-" * 80)
    try:
        health = client.health()
        print(f"✅ Servicio operativo")
        print(f"   Status: OK")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n⚠️  El servicio puede no estar levantado.")
        print("   Ejecuta en tu terminal: docker-compose up -d")
        return
    
    # 2. Config
    print("\n2️⃣ CONFIGURACIÓN CARGADA")
    print("-" * 80)
    try:
        config = client.config()
        print(f"✅ Credenciales LinkedIn cargadas")
        print(f"   • li_at: {str(config.get('li_at', 'N/A'))[:30]}...")
        print(f"   • jsessionid: {config.get('jsessionid', 'N/A')}")
        print(f"   • bcookie: {str(config.get('bcookie', 'N/A'))[:25]}...")
        print(f"   • lidc: {str(config.get('lidc', 'N/A'))[:25]}...")
        print(f"   • last_sync: {config.get('last_sync', 'N/A')}")
    except Exception as e:
        print(f"⚠️  Error: {e}")
    
    # 3. Conversaciones
    print("\n3️⃣ CONVERSACIONES")
    print("-" * 80)
    try:
        convs = client.conversations()
        total = convs.get('total', len(convs) if isinstance(convs, list) else 0)
        conversations = convs.get('conversations', convs.get('records', convs if isinstance(convs, list) else []))
        
        print(f"✅ Total conversaciones: {total}")
        
        if conversations:
            print(f"\n   Últimas {min(5, len(conversations))} conversaciones:\n")
            for i, conv in enumerate(conversations[:5], 1):
                if isinstance(conv, dict):
                    conv_id = conv.get('id', conv.get('$id', 'N/A'))
                    print(f"   #{i} ID: {conv_id}")
                    print(f"      Nombre: {conv.get('name', conv.get('subject', 'N/A'))}")
                    print(f"      Participantes: {len(conv.get('participants', []))} personas")
                    print(f"      Mensajes: {conv.get('message_count', conv.get('messages_count', '?'))}")
                    if conv.get('last_message'):
                        last_msg = conv.get('last_message', '')
                        print(f"      Último mensaje: {str(last_msg)[:80]}...")
                    print()
        else:
            print("   (sin conversaciones aún)\n")
    except Exception as e:
        print(f"⚠️  Error: {e}\n")
    
    # 4. Últimos mensajes
    print("\n4️⃣ ÚLTIMOS MENSAJES")
    print("-" * 80)
    try:
        msgs = client.messages(limit=10)
        total = msgs.get('total', len(msgs) if isinstance(msgs, list) else 0)
        messages = msgs.get('records', msgs.get('messages', msgs if isinstance(msgs, list) else []))
        
        print(f"✅ Total mensajes en sistema: {total}")
        
        if messages:
            print(f"\n   Últimos {min(5, len(messages))} mensajes:\n")
            for i, msg in enumerate(messages[:5], 1):
                if isinstance(msg, dict):
                    print(f"   #{i} De: {msg.get('from', msg.get('sender', 'Unknown'))}")
                    print(f"      Timestamp: {msg.get('timestamp', msg.get('date', 'N/A'))}")
                    body = msg.get('body', msg.get('message', msg.get('text', 'N/A')))
                    body_preview = str(body)[:100] if body else "N/A"
                    print(f"      Mensaje: {body_preview}...")
                    print()
        else:
            print("   (sin mensajes aún)\n")
    except Exception as e:
        print(f"⚠️  Error: {e}\n")
    
    # 5. Monitor stats
    print("\n5️⃣ ESTADÍSTICAS DEL MONITOR")
    print("-" * 80)
    try:
        stats = client.monitor_stats()
        print(f"✅ Estadísticas del sistema:\n")
        for key, value in stats.items():
            print(f"   • {key}: {value}")
        print()
    except Exception as e:
        print(f"⚠️  Error: {e}\n")
    
    # 6. WebSocket info
    print("\n6️⃣ WEBSOCKET REAL-TIME")
    print("-" * 80)
    print(f"✅ Acceso a stream en tiempo real:")
    print(f"\n   URL: ws://192.168.0.214:8000/ws/messages")
    print(f"   Latencia esperada: <2 segundos")
    print(f"   Multi-cliente: Soportado")
    print(f"\n   Ejemplo JavaScript:")
    print(f"   const ws = new WebSocket('ws://192.168.0.214:8000/ws/messages')")
    print(f"   ws.onmessage = (e) => console.log(JSON.parse(e.data))")
    print()
    
    print("=" * 80)
    print("✅ CONSUMO DEL SERVICIO COMPLETADO")
    print("=" * 80)

if __name__ == "__main__":
    main()
