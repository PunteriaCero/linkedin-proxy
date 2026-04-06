# Estado de Prueba: Obtener Conversaciones de LinkedIn

**Fecha:** 2026-04-06  
**Status:** Esperando código 2FA

## Progreso

✅ **Instaladas dependencias:**
- fastapi, uvicorn, httpx, requests
- linkedin-api, pyppeteer
- python-multipart, pydantic

✅ **Guardadas credenciales:**
- Email: punteriacero.hernan@gmail.com
- Password: ******* (guardado en .linkedin_creds.json)

❌ **Login automático failed:**
- Razón: LinkedIn pidió 2FA
- Archivo: run_linkedin_test.py

⏳ **Esperando:**
- Código de verificación 2FA (6 dígitos)
- Cuando se reciba, ejecutar: complete_login_2fa.py

## Scripts Creados

1. **run_linkedin_test.py** - Login automático (sin 2FA)
2. **complete_login_2fa.py** - Login con código 2FA
3. **get_linkedin_chats.py** - Manual con credenciales
4. **test_conversations.py** - Manual con credenciales

## Próximos Pasos

1. Esperar código 2FA de Hernan
2. Ejecutar: `python3 complete_login_2fa.py <codigo>`
3. Script completará login + extraerá cookies
4. Mostrará últimas 10 conversaciones

## Credenciales Guardadas

- Ubicación: /home/node/.openclaw/workspace/linkedin-n8n-gateway/.linkedin_creds.json
- Contenido: email + password (local, no en git)
