#!/usr/bin/env python3
"""
Script para obtener conversaciones de LinkedIn
Automatiza login + obtiene conversaciones recientes
"""

import asyncio
import sys
import json
from datetime import datetime

# Importar el módulo de login
from linkedin_login import login_and_extract_cookies_sync
from linkedin_api import Linkedin

async def get_conversations_async(email: str, password: str):
    """Obtener conversaciones usando login automático"""
    
    print("\n🔐 LinkedIn Conversation Extractor")
    print("=" * 70)
    
    # Paso 1: Login automático
    print(f"\n📡 Iniciando sesión automática para: {email}")
    try:
        cookies = await login_and_extract_cookies(email, password, timeout=120)
        print("✅ Login exitoso - Cookies obtenidas")
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return False
    
    # Verificar cookies
    if not cookies.get('li_at') or not cookies.get('jsessionid'):
        print("❌ No se extrajeron cookies válidas")
        return False
    
    print(f"   li_at: {cookies['li_at'][:30]}...")
    print(f"   jsessionid: {cookies['jsessionid'][:30]}...")
    
    # Paso 2: Conectar a LinkedIn
    print("\n📨 Conectando a LinkedIn API...")
    try:
        client = Linkedin(
            username=None,
            password=None,
            cookies={
                'li_at': cookies.get('li_at'),
                'JSESSIONID': cookies.get('jsessionid'),
                'bcookie': cookies.get('bcookie', ''),
                'lidc': cookies.get('lidc', '')
            }
        )
        print("✅ Conectado a LinkedIn")
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return False
    
    # Paso 3: Obtener conversaciones
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
                print(f"   Último: [Error obteniendo mensaje]")
        
        print("\n" + "=" * 70)
        print("✅ Test completado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo conversaciones: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Uso: python3 get_linkedin_chats.py <email> <password>")
        print("Ejemplo: python3 get_linkedin_chats.py tu@email.com tucontraseña")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    # Ejecutar async
    try:
        success = asyncio.run(get_conversations_async(email, password))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
