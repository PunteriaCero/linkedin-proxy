#!/usr/bin/env python3
"""
Portainer Stack Deployer
Despliega el servicio LinkedIn API en Portainer
"""

import json
import urllib.request
import urllib.error
import sys

def portainer_deploy():
    print("🐳 DESPLEGANDO EN PORTAINER")
    print("=" * 70)
    
    PORTAINER_URL = "http://192.168.0.214:9000"
    API_URL = f"{PORTAINER_URL}/api"
    
    print(f"\n1️⃣ CONECTANDO A PORTAINER")
    print("-" * 70)
    print(f"URL: {PORTAINER_URL}\n")
    
    # Paso 1: Listar endpoints para ver si está disponible
    try:
        req = urllib.request.Request(f"{API_URL}/endpoints", method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            print("✅ Portainer responde")
            print(f"   HTTP {response.status}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("❌ Portainer requiere autenticación (HTTP 401)")
            print("\n   SOLUCIÓN:")
            print("   1. Abre: http://192.168.0.214:9000")
            print("   2. Ingresa usuario y contraseña")
            print("   3. Luego ejecuta este script nuevamente")
            print("\n   O usa: docker-compose up -d (sin autenticación)")
            return False
        else:
            print(f"❌ Error HTTP {e.code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n   ALTERNATIVA: Usa docker-compose")
        print("   $ docker-compose up -d")
        return False
    
    # Paso 2: Obtener el docker-compose.yml
    print("\n2️⃣ PREPARANDO STACK")
    print("-" * 70)
    
    try:
        with open('docker-compose.yml', 'r') as f:
            compose_content = f.read()
        print("✅ docker-compose.yml cargado")
    except FileNotFoundError:
        print("❌ docker-compose.yml no encontrado")
        print("   Asegúrate de estar en: /home/node/.openclaw/workspace/linkedin-n8n-gateway")
        return False
    
    # Paso 3: Información del stack
    print("\n3️⃣ INFORMACIÓN DEL STACK")
    print("-" * 70)
    
    stack_name = "linkedin-api-gateway"
    print(f"Nombre: {stack_name}")
    print(f"Servicio: IA_linkedin_api")
    print(f"Puerto: 8000")
    print(f"Imagen: linkedin-api:latest")
    
    print("\n4️⃣ INSTRUCCIONES MANUALES EN PORTAINER UI")
    print("-" * 70)
    print("""
    Para crear el stack manualmente en Portainer:
    
    1. Abre: http://192.168.0.214:9000
    2. Login con tus credenciales
    3. Ve a: Stacks (o Compose)
    4. Click: "+ Add Stack" o "Create Stack"
    5. Nombre: linkedin-api-gateway
    6. Pega el contenido de docker-compose.yml
    7. Click: "Deploy"
    
    O vía API con token (requiere autenticación previa)
    """)
    
    print("\n5️⃣ ALTERNATIVA RECOMENDADA")
    print("-" * 70)
    print("""
    Usa docker-compose directamente (sin Portainer):
    
    $ docker-compose up -d
    
    Ventajas:
    ✓ Sin autenticación
    ✓ Más rápido
    ✓ Más directo
    ✓ Fácil de monitorear
    """)
    
    return True

if __name__ == "__main__":
    success = portainer_deploy()
    sys.exit(0 if success else 1)
