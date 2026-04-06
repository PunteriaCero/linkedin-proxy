#!/usr/bin/env python3
"""
Script para completar login de LinkedIn con código 2FA
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Importar módulos interactivos
try:
    from linkedin_interactive import start_login_with_2fa, complete_login_with_code
except ImportError:
    print("❌ linkedin_interactive module no encontrado")
    sys.exit(1)

from linkedin_api import Linkedin

async def login_with_2fa_code(email: str, password: str, code_2fa: str):
    """Completar login con código 2FA"""
    
    print("\n🔐 LinkedIn Login con 2FA")
    print("=" * 70)
    
    print(f"📧 Email: {email}")
    print(f"🔐 Código 2FA: {code_2fa}")
    
    # Crear session ID único
    session_id = f"session_{int(datetime.now().timestamp())}"
    
    # Paso 1: Iniciar login
    print(f"\n📡 Iniciando sesión...")
    try:
        result = await start_login_with_2fa(email, password, session_id)
        print(f"✅ {result.get('message', 'Esperando 2FA...')}")
    except Exception as e:
        print(f"❌ Error iniciando login: {e}")
        return False
    
    # Paso 2: Completar con código 2FA
    print(f"\n✅ Completando login con código 2FA...")
    try:
        cookies = await complete_login_with_code(session_id, code_2fa)
        print("✅ Login completado exitosamente")
    except Exception as e:
        print(f"❌ Error completando login: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verificar cookies
    if not cookies.get('li_at') or not cookies.get('jsessionid'):
        print("❌ No se extrajeron cookies válidas")
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
    if len(sys.argv) < 2:
        print("Uso: python3 complete_login_2fa.py <codigo_2fa>")
        print("Ejemplo: python3 complete_login_2fa.py 123456")
        sys.exit(1)
    
    code_2fa = sys.argv[1].strip()
    
    # Leer credenciales
    creds_file = Path(".linkedin_creds.json")
    if not creds_file.exists():
        print(f"❌ {creds_file} no encontrado")
        sys.exit(1)
    
    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
        email = creds.get('linkedin_email')
        password = creds.get('linkedin_password')
    except:
        print("❌ Error leyendo credenciales")
        sys.exit(1)
    
    # Ejecutar async
    try:
        success = asyncio.run(login_with_2fa_code(email, password, code_2fa))
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
