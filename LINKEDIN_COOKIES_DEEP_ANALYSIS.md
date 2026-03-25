# LinkedIn Cookies Deep Analysis

## 🔍 Investigación: Por qué LinkedIn Rechaza las Cookies

### La Realidad de linkedin-api

La librería `linkedin-api` es un wrapper alrededor de los endpoints **Voyager** internos de LinkedIn. Sin embargo, hay varios requerimientos críticos que debe cumplir:

---

## 1. Headers Requeridos por LinkedIn

### Headers por Defecto (en client.py)

LinkedIn requiere estos headers para aceptar requests:

```python
REQUEST_HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
    "accept-language": "en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "x-li-lang": "en_US",
    "x-restli-protocol-version": "2.0.0",
}
```

**Importante:** Si LinkedIn ve un User-Agent sospechoso (bot, curl, etc.), puede rechazar la conexión.

### El Header CSRF-Token

**CRÍTICO:** Cuando usas cookies en lugar de autenticación normal, LinkedIn requiere:

```python
self.session.headers["csrf-token"] = self.session.cookies["JSESSIONID"].strip('"')
```

Este header debe contener el valor de JSESSIONID sin comillas.

---

## 2. El Flujo de Autenticación con Cookies

### Cómo linkedin-api lo Hace

En `client.py` línea 95:

```python
def _set_session_cookies(self, cookies):
    """
    Set cookies of the current session and save them to a file.
    """
    self.session.cookies = cookies  # Establece cookies en la sesión
    self.session.headers["csrf-token"] = self.session.cookies["JSESSIONID"].strip('"')  # ← CRÍTICO
```

**Esto se ejecuta automáticamente cuando:**
- Pasas `authenticate=False` + `cookies={...}` al constructor

**Si no ocurre, get_profile() fallará con HTTP 403.**

---

## 3. Por Qué sigue Fallando

### Posibles Causas

1. **LinkedIn te identifica como bot**
   - Detecta User-Agent no válido
   - Detecta múltiples requests muy rápido
   - Detecta IP con patrón sospechoso

2. **Cambios en la API de LinkedIn**
   - LinkedIn cambió estructura de voyager
   - Requiere headers adicionales no documentados
   - Requiere metadata específica de navegador

3. **Tu Cuenta Tiene Restricciones**
   - LinkedIn bloqueó tu IP
   - LinkedIn detectó actividad sospechosa
   - Tu cuenta requiere verificación 2FA
   - Cookies creadas pero no validadas en primer login

4. **Estructura de Cookies Incompleta**
   - Falta cookie de sesión adicional
   - Cookies incompletas (copié cortadas)
   - Cookies de diferentes navegadores (mismatch)

---

## 4. Cookies Reales vs Las Que Necesita LinkedIn

### En DevTools Ves

```
li_at: "AbC123xyz..."
JSESSIONID: "1234567890ABCDEF"
```

### Pero LinkedIn también Requiere (No Siempre Visible)

Internamente, LinkedIn mantiene:
- `bcookie` - Browser cookie (identificación de navegador)
- `aam_uuid` - Audience Manager UUID
- `lidc` - LinkedIn Data Center identifier
- `UserMatchHistory` - Tracking
- `lms_analytics` - Analytics
- Otras cookies de seguimiento

**Cuando copias SOLO li_at + JSESSIONID, LinkedIn puede rechazarlas porque faltan cookies complementarias.**

---

## 5. Soluciones Reales

### Opción 1: Obtener Cookies Completas (Recomendado)

No copies SOLO li_at + JSESSIONID. Copia TODAS las cookies de LinkedIn:

**En Chrome DevTools:**
1. Abre LinkedIn
2. DevTools → Application → Cookies → linkedin.com
3. Haz click derecho en la lista de cookies
4. Si hay opción "Copy all as cURL" → usa eso
5. Si no, copia TODAS las cookies visibles, no solo 2

**Las cookies críticas además de li_at + JSESSIONID:**
- `bcookie` - IMPORTANTE
- `lidc` - IMPORTANTE
- `UserMatchHistory` - Útil

### Opción 2: Usar Cookies de Incógnito Correctamente

```
1. Abre LinkedIn en pestaña INCÓGNITO (no privada)
2. Inicia sesión COMPLETAMENTE
3. Espera 30 segundos (LinkedIn procesa verificación)
4. Entonces copia las cookies
5. Las cookies de incógnito deben incluir TODAS las de arriba
```

### Opción 3: Verificar que LinkedIn No te Bloqueó

LinkedIn bloquea IPs que:
- Hacen requests muy rápido
- Usan VPN/Proxy sospechoso
- Intentan acceder sin User-Agent válido
- Hacen scraping obvio

**Para verificar:**
1. Abre LinkedIn en navegador normal
2. ¿Funciona?
   - NO → Tu IP está bloqueada. Usa VPN o espera 24h
   - SÍ → Continúa

---

## 6. El Problema Técnico Subyacente

### Por Qué linkedin-api Está Limitado

La librería `linkedin-api` funciona porque:
- Mantiene User-Agents realistas
- Establece csrf-token correctamente
- Simula delays entre requests (evade())
- Usa endpoints Voyager internos

Pero FALLA cuando:
- LinkedIn cambió estructura (sucede cada 2-3 meses)
- Tu cuenta tiene restricciones
- Faltan cookies complementarias
- IP está bloqueada

### Alternativa: Usando Voyager API Directamente

Si quieres más control, puedes hacer requests HTTP directos:

```python
import requests

cookies = {
    'li_at': '...',
    'JSESSIONID': '...',
    'bcookie': '...',  # ← Importante
    'lidc': '...',
}

headers = {
    'User-Agent': 'Mozilla/5.0...',
    'csrf-token': cookies['JSESSIONID'].strip('"'),
    'x-restli-protocol-version': '2.0.0',
}

# Hacer request a Voyager
response = requests.get(
    'https://www.linkedin.com/voyagerGraphQL?action=getProfile',
    cookies=cookies,
    headers=headers
)
```

Esto te daría más visibilidad sobre qué está fallando exactamente.

---

## 7. Recomendaciones Finales

### Paso a Paso para Resolver

1. **Verifica que LinkedIn funcione en navegador**
   - Si no funciona → espera 24h (IP bloqueada)
   - Si sí funciona → continúa

2. **Obtén cookies COMPLETAS (no solo 2)**
   - Usa "Copy all as cURL" si disponible
   - O copia TODAS las visible en DevTools
   - O usa script Python con `requests_html`

3. **Prueba estructura mínima necesaria**
   - li_at (sesión)
   - JSESSIONID (sesión)
   - bcookie (browser)
   - lidc (data center)

4. **Si aun así falla, considera**
   - Usar `playwright` o `selenium` para automatizar login
   - Hacer requests HTTP directos con todas las cookies
   - Implementar Voyager API wrapper personalizado

---

## 8. Status Actual

- ❌ linkedin-api funciona para algunos, no para otros
- ❌ Causas múltiples: IP, cookies incompletas, account restrictions
- ✅ La app maneja errores correctamente
- ✅ Mensaje de usuario mejorado con soluciones

### Próximo Paso Recomendado

**Probar con cookies COMPLETAS (no solo li_at + JSESSIONID):**

Si LinkedIn aún rechaza → Problema probable:
- IP bloqueada (espera o usa VPN)
- Account requiere verificación (completa verificación en navegador)
- linkedin-api incompatible con estructura actual (migrar a Voyager directo)
