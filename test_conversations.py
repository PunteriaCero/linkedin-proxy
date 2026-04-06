#!/usr/bin/env python3
"""
Test Script: Obtener conversaciones recientes de LinkedIn
Uso: python3 test_conversations.py <li_at> <jsessionid>
"""

import json
import sys
from datetime import datetime
from linkedin_api import Linkedin

def test_linkedin_conversations(li_at, jsessionid):
    """Conectar a LinkedIn y obtener conversaciones"""
    
    print("\n🔐 LinkedIn Conversation Tester")
    print("=" * 70)
    
    if not li_at or not jsessionid:
        print("❌ Falta parámetros. Uso:")
        print("   python3 test_conversations.py <li_at> <jsessionid>")
        return False
    
    # Conectar
    print("\n📡 Conectando a LinkedIn...")
    try:
        client = Linkedin(
            username=None,
            password=None,
            cookies={
                'li_at': li_at,
                'JSESSIONID': jsessionid
            }
        )
        print("✅ Conectado a LinkedIn")
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return False
    
    # Obtener conversaciones
    print("\n📨 Obteniendo conversaciones recientes...")
    try:
        conversations = client.get_conversations()
        
        if not conversations:
            print("⚠️ No hay conversaciones")
            return True
        
        print(f"✅ {len(conversations)} conversaciones encontradas\n")
        
        # Mostrar últimas 10 conversaciones
        print("📍 ÚLTIMAS CONVERSACIONES:")
        print("=" * 70)
        
        for i, conv in enumerate(conversations[:10], 1):
            conv_id = conv.get('conversationId', 'N/A')
            
            # Obtener participantes
            participants = conv.get('participants', [])
            participant_name = participants[0].get('name', 'Unknown') if participants else 'Unknown'
            
            # Timestamp
            created_at = conv.get('createdAt', 'N/A')
            if isinstance(created_at, (int, float)):
                created_at = datetime.fromtimestamp(created_at/1000).strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n{i}. {participant_name}")
            print(f"   ID: {conv_id[:45]}...")
            print(f"   Creado: {created_at}")
            
            # Intentar obtener mensaje más reciente
            try:
                details = client.get_conversation_details(conv_id)
                elements = details.get('elements', [])
                if elements:
                    last_msg = elements[0]
                    msg_body = last_msg.get('eventContent', {}).get('com.linkedin.voyager.messaging.event.MessageEvent', {}).get('body', 'N/A')
                    sender = last_msg.get('from', 'N/A')
                    print(f"   Último: {msg_body[:65]}...")
                    print(f"   De: {sender}")
            except Exception as e:
                print(f"   Último: [Error obteniendo mensaje]")
        
        print("\n" + "=" * 70)
        print("✅ Test completado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo conversaciones: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 test_conversations.py <li_at> <jsessionid>")
        sys.exit(1)
    
    li_at = sys.argv[1]
    jsessionid = sys.argv[2]
    
    success = test_linkedin_conversations(li_at, jsessionid)
    sys.exit(0 if success else 1)
