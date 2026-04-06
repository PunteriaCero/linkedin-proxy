#!/usr/bin/env python3
"""
Script para obtener conversaciones de LinkedIn
Usa credenciales directamente sin Pyppeteer/navegador
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from linkedin_api import Linkedin

def get_conversations_direct():
    """Obtener conversaciones usando email + password directamente"""
    
    print("\n🔐 LinkedIn Conversation Extractor (DIRECT AUTH)")
    print("=" * 70)
    
    # Leer credenciales
    creds_file = Path(".linkedin_creds.json")
    if not creds_file.exists():
        print(f"❌ {creds_file} no encontrado")
        return False
    
    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
        email = creds.get('linkedin_email')
        password = creds.get('linkedin_password')
        
        if not email or not password:
            print("❌ Credenciales incompletas")
            return False
        
        print(f"📧 Email: {email}")
    except Exception as e:
        print(f"❌ Error leyendo credenciales: {e}")
        return False
    
    # Conectar con email + password (linkedin-api lo maneja internamente)
    print("\n📡 Conectando a LinkedIn...")
    try:
        client = Linkedin(email, password)
        print("✅ Conectado a LinkedIn")
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        print(f"   Puede ser: 2FA activo, contraseña incorrecta, IP bloqueada")
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
                    if sender:
                        print(f"   De: {sender}")
            except Exception as e:
                pass
        
        print("\n" + "=" * 70)
        print("✅ Test completado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo conversaciones: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = get_conversations_direct()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
