#!/usr/bin/env python3
"""
Checklist Rápido - LinkedIn-n8n Gateway
Script para verificar que todo está listo para usar.
"""

import os
import sys
import json
from pathlib import Path

def check(condition, message):
    """Imprime un check ✅ o ❌"""
    symbol = "✅" if condition else "❌"
    print(f"{symbol} {message}")
    return condition

def main():
    print("\n" + "="*60)
    print("🔍 CHECKLIST RÁPIDO - LINKEDIN-N8N GATEWAY")
    print("="*60 + "\n")
    
    all_good = True
    
    # 1. Archivos principales
    print("📄 Archivos Principales:")
    all_good &= check(os.path.exists("main.py"), "main.py existe")
    all_good &= check(os.path.exists("test_gateway.py"), "test_gateway.py existe")
    all_good &= check(os.path.exists("requirements.txt"), "requirements.txt existe")
    
    # 2. Documentación
    print("\n📚 Documentación:")
    all_good &= check(os.path.exists("README.md"), "README.md existe")
    all_good &= check(os.path.exists("FLOW_SIMULATION.md"), "FLOW_SIMULATION.md existe")
    all_good &= check(os.path.exists("DEPLOYMENT.md"), "DEPLOYMENT.md existe")
    all_good &= check(os.path.exists("DELIVERY.md"), "DELIVERY.md existe")
    
    # 3. Scripts
    print("\n🚀 Scripts:")
    all_good &= check(os.path.exists("start.sh"), "start.sh existe")
    all_good &= check(os.path.exists("config.example.json"), "config.example.json existe")
    
    # 4. Virtual Environment
    print("\n📦 Dependencias:")
    all_good &= check(os.path.exists("venv"), "venv/ directorio existe")
    
    # 5. Permisos
    print("\n🔐 Permisos:")
    all_good &= check(os.access("start.sh", os.X_OK), "start.sh es ejecutable")
    
    # 6. Contenido de requirements.txt
    print("\n📋 Contenido de requirements.txt:")
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", "r") as f:
            content = f.read()
            all_good &= check("fastapi" in content, "fastapi en requirements")
            all_good &= check("uvicorn" in content, "uvicorn en requirements")
            all_good &= check("linkedin-api" in content, "linkedin-api en requirements")
            all_good &= check("httpx" in content, "httpx en requirements")
    
    # 7. Resumen
    print("\n" + "="*60)
    if all_good:
        print("✅ TODO ESTÁ LISTO PARA USAR")
        print("\nProximos pasos:")
        print("  1. source venv/bin/activate")
        print("  2. python3 test_gateway.py")
        print("  3. python3 main.py")
        print("  4. Abre http://localhost:8000/admin")
        return 0
    else:
        print("⚠️ ALGUNOS ELEMENTOS FALTAN")
        print("Verifica el directorio y los archivos arriba.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
