#!/usr/bin/env python3
"""
Script para obtener conversaciones de LinkedIn
Lee credenciales desde .linkedin_creds.json
"""

import asyncio
import sys
import json
import os
from datetime import datetime
from pathlib import Path

# Importar el módulo de login
try:
    from linkedin_login import login_and_extract_cookies
except ImportError:
    print("❌ linkedin_login module no encontrado")
    sys.exit(1)

from linkedin_api import Linkedin

async def get_conversations_auto():
    """Obtener conversaciones usando login automático"""
    
    print("\n🔐 LinkedIn Conversation Extractor (AUTO)")
    print("=" * 70)
    
    # Paso 1: Leer credenciales
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
            print("❌ Credenciales incompletas en .linkedin_creds.json")
            return False
        
        print(f"📧 Email: {email}")
        print(f"🔑 Contraseña: {'*' * len(password)}")
    except json.JSONDecodeError:
        print("❌ Error leyendo .linkedin_creds.json")
        return False
    
    # Paso 2: Login automático
    print(f"\n📡 Iniciando sesión automática...")
    print("   (Esto abrirá un navegador automáticamente)")
    
    try:
        cookies = await login_and_extract_cookies(email, password, timeout=120)
        print("✅ Login exitoso - Cookies obtenidas")
    except Exception as e:
        print(f"❌ Error en login: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verificar cookies
    if not cookies.get('li_at') or not cookies.get('jsessionid'):
        print("❌ No se extrajeron cookies válidas")
        print(f"   Cookies obtenidas: {list(cookies.keys())}")
        return False
    
    print(f"   li_at: {cookies['li_at'][:30]}...")
    print(f"   jsessionid: {cookies['jsessionid'][:30]}...")
    
    # Paso 3: Conectar a LinkedIn
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
    
    # Paso 4: Obtener conversaciones
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


def main():
    """Main entry point"""
    try:
        success = asyncio.run(get_conversations_auto())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
