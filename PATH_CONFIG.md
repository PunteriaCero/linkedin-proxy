# Path Configuration - Docker VOLUMEs Integration

## 🎯 Objetivo

Adaptar la lógica de la aplicación para usar las nuevas rutas de VOLUMEs de Docker, permitiendo que:
- Logs se escriban en `/app/logs/` (accesible desde host)
- Configuración se almacene en `/app/config/` (persistente)
- Datos se guarden en `/app/data/` (futuro almacenamiento)

---

## 📋 CAMBIOS EN main.py

### Antes (rutas locales)
```python
CONFIG_FILE = "config.json"
PROCESSED_MESSAGES_FILE = "processed_messages.json"

logging.basicConfig(
    handlers=[
        logging.FileHandler('gateway.log'),
        ...
    ]
)
```

**Problemas:**
- ❌ Archivos en raíz del contenedor
- ❌ No respetan VOLUMEs
- ❌ Logs no accesibles desde host
- ❌ Config se pierde si borras contenedor

---

### Después (rutas con VOLUMEs)
```python
CONFIG_DIR = Path("/app/config") if os.path.exists("/app/config") else Path(".")
LOGS_DIR = Path("/app/logs") if os.path.exists("/app/logs") else Path(".")
DATA_DIR = Path("/app/data") if os.path.exists("/app/data") else Path(".")

# Crear directorios si no existen
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Usar rutas explícitas
CONFIG_FILE = str(CONFIG_DIR / "config.json")
PROCESSED_MESSAGES_FILE = str(DATA_DIR / "processed_messages.json")
LOG_FILE = str(LOGS_DIR / "gateway.log")

logging.basicConfig(
    handlers=[
        logging.FileHandler(LOG_FILE),
        ...
    ]
)
```

**Mejoras:**
- ✅ Usa rutas de VOLUMEs si existen
- ✅ Fallback a rutas locales para desarrollo
- ✅ Crea directorios automáticamente
- ✅ Logs accesibles en ./logs/gateway.log desde host
- ✅ Config persiste en ./config/config.json
- ✅ Datos guardan en ./data/processed_messages.json

---

## 📂 ESTRUCTURA DE RUTAS

### En Desarrollo (sin Docker)
```
proyecto/
├── config.json                      # Se crea aquí
├── processed_messages.json          # Se crea aquí
├── gateway.log                      # Se crea aquí
└── main.py
```

**Rutas usadas:**
- CONFIG_FILE = "./config.json"
- PROCESSED_MESSAGES_FILE = "./processed_messages.json"
- LOG_FILE = "./gateway.log"

---

### En Producción (con Docker)
```
host/
├── config/
│   └── config.json                  # VOLUME /app/config
├── logs/
│   └── gateway.log                  # VOLUME /app/logs
├── data/
│   └── processed_messages.json      # VOLUME /app/data
└── docker-compose.yml

contenedor/
├── /app/config/config.json
├── /app/logs/gateway.log
└── /app/data/processed_messages.json
```

**Rutas usadas:**
- CONFIG_FILE = "/app/config/config.json"
- PROCESSED_MESSAGES_FILE = "/app/data/processed_messages.json"
- LOG_FILE = "/app/logs/gateway.log"

---

## 🔄 FLUJO DE EJECUCIÓN

### 1. Startup
```
1. App inicia
2. Detecta si /app/config, /app/logs, /app/data existen
3. Si existen (Docker) → usa esas rutas
4. Si no existen (dev local) → usa rutas locales
5. Crea directorios si no existen
6. Inicia logging a archivo
```

### 2. Config Load
```
load_config():
  1. Intenta leer de CONFIG_FILE
  2. Si no existe → usa DEFAULT_CONFIG
  3. Config cargada desde /app/config/config.json (prod)
     o ./config.json (dev)
```

### 3. Log Writing
```
logger.info("message"):
  1. Escribe a stdout (siempre)
  2. Escribe a /app/logs/gateway.log (prod)
     o ./gateway.log (dev)
  3. Archivo accesible desde host en prod
```

### 4. Message Processing
```
load_processed_messages():
  1. Lee de /app/data/processed_messages.json (prod)
     o ./processed_messages.json (dev)
  2. Mantiene estado de mensajes sincronizados
  3. Persiste cambios en mismo archivo
```

---

## ✅ COMPATIBILIDAD

### ✓ Development (sin Docker)
```bash
# Simplemente ejecuta
python3 main.py

# Archivos se crean localmente
ls -la *.json gateway.log
```

### ✓ Docker Compose
```bash
# Ejecuta
docker-compose up -d

# Archivos accesibles desde host
ls -la logs/gateway.log
ls -la config/config.json
ls -la data/processed_messages.json
```

### ✓ Docker CLI
```bash
docker run -d \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  linkedin-gateway:latest

# Archivos accesibles
ls -la logs/
```

### ✓ Kubernetes
```yaml
volumes:
  - name: logs
    emptyDir: {}
  - name: config
    configMap:
      name: gateway-config
  - name: data
    persistentVolumeClaim:
      claimName: gateway-data
```

---

## 🎯 BENEFICIOS

| Aspecto | Antes | Después |
|---------|-------|---------|
| Logs accesibles | ❌ Dentro contenedor | ✅ ./logs/gateway.log |
| Config persistente | ⚠️ Si o no | ✅ ./config/ siempre |
| Datos guardados | ⚠️ Si o no | ✅ ./data/ siempre |
| Desarrollo local | ✅ Fácil | ✅ Fácil (mismo código) |
| Producción | ⚠️ Complejidad | ✅ Automático |
| Múltiples instancias | ❌ Comparte estado | ✅ Volúmenes separados |
| Backup | ❌ Complejidad | ✅ `cp -r logs/ config/` |

---

## 🔐 PERMISOS

La aplicación corre como `root` en Docker, permitiendo:
- ✓ Escribir en todos los directorios
- ✓ Crear archivos con permisos correctos
- ✓ Cambiar propietario si es necesario

---

## 📝 NOTAS

1. **Fallback a desarrollo local:**
   ```python
   CONFIG_DIR = Path("/app/config") if os.path.exists("/app/config") else Path(".")
   ```
   Esto permite ejecutar el mismo código en dev (local) y prod (Docker).

2. **Creación automática de directorios:**
   ```python
   CONFIG_DIR.mkdir(parents=True, exist_ok=True)
   ```
   No necesitas crearlos manualmente.

3. **Path como string:**
   ```python
   CONFIG_FILE = str(CONFIG_DIR / "config.json")
   ```
   Convierte Path a string para compatibilidad con logging.FileHandler()

---

## ✨ RESULTADO FINAL

La aplicación ahora:
- ✅ Respeta VOLUMEs de Docker
- ✅ Logs accesibles desde host
- ✅ Config y data persisten
- ✅ Compatible con desarrollo local
- ✅ Compatible con Docker y Kubernetes
- ✅ Manejo automático de rutas
