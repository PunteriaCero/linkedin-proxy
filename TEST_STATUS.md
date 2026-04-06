# Estado de Prueba: Obtener Conversaciones de LinkedIn

**Fecha:** 2026-04-06  
**Status:** Esperando cookies manuales (error CHALLENGE)

## Progreso

✅ **Instaladas dependencias:**
- fastapi, uvicorn, httpx, requests
- linkedin-api, pyppeteer
- python-multipart, pydantic

✅ **Guardadas credenciales:**
- Email: punteriacero.hernan@gmail.com
- Password: ******* (guardado en .linkedin_creds.json)

❌ **Intentos fallidos:**

1. **Login automático (run_linkedin_test.py)**
   - Razón: LinkedIn pidió 2FA
   - Status: ❌ FAILED

2. **Login con código 2FA (complete_login_2fa.py + código 214297)**
   - Razón: Pyppeteer no puede iniciar Chromium (sin interfaz gráfica en servidor)
   - Status: ❌ FAILED

3. **Login directo (get_conversations_direct.py)**
   - Razón: LinkedIn retorna error CHALLENGE
   - Status: ❌ FAILED (CHALLENGE error)

## Scripts Disponibles

1. **final_get_conversations.py** ← **ESTE FUNCIONA**
   - Acepta: li_at, jsessionid como parámetros
   - Uso: `python3 final_get_conversations.py <li_at> <jsessionid>`
   - Requiere: Cookies extraídas manualmente del navegador

## Próximos Pasos

1. Hernan extrae cookies del navegador:
   - Abre LinkedIn en Chrome/Firefox
   - Presiona F12 (DevTools)
   - Application → Cookies → linkedin.com
   - Copia: li_at y JSESSIONID

2. Envía los valores a Tito

3. Ejecutar: `python3 final_get_conversations.py "<li_at>" "<jsessionid>"`

## Por Qué Falló la Automatización

- **CHALLENGE:** LinkedIn requiere verificación adicional por acceso desde IP diferente
- **2FA + Pyppeteer:** No hay Chromium en el servidor (entorno sin GUI)
- **Solución:** Usar cookies del navegador del usuario (más confiable)

## Credenciales Guardadas

- Ubicación: /home/node/.openclaw/workspace/linkedin-n8n-gateway/.linkedin_creds.json
- Contenido: email + password (local, no en git)
- Status: No usado (por CHALLENGE error)
