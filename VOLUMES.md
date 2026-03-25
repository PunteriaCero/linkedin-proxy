# Docker Volumes Guide

## 🎯 Objetivo

Los archivos de configuración y logs persisten fuera del contenedor, incluso después de que este finalice o sea eliminado.

---

## 📂 VOLÚMENES CONFIGURADOS

### 1. **Logs** (`/app/logs`)
- **Contenedor:** `/app/logs/`
- **Host:** `./logs/`
- **Archivos:** gateway.log
- **Acceso:** Lectura/Escritura
- **Propósito:** Debugging y monitoreo

### 2. **Configuración** (root `/app/`)
- **config.json** → configuración de LinkedIn + n8n
- **processed_messages.json** → historial de mensajes sincronizados
- **Propósito:** Persistencia de estado

### 3. **Data** (`/app/data`)
- **Contenedor:** `/app/data/`
- **Host:** `./data/`
- **Propósito:** Almacenamiento futuro (bases datos, caché, etc.)

---

## 🚀 CÓMO USAR

### Con Docker Compose (RECOMENDADO)

```bash
docker-compose up -d
```

Automáticamente:
- ✅ Crea directorios `logs/`, `data/`
- ✅ Monta volúmenes
- ✅ Archivo gateway.log accesible en `./logs/gateway.log`

### Con Docker CLI

```bash
docker run -d \
  --name linkedin-gateway \
  -p 8000:8000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/processed_messages.json:/app/processed_messages.json \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  linkedin-gateway:latest
```

---

## 📊 ESTRUCTURA DE DIRECTORIOS

Después de ejecutar `docker-compose up`:

```
project-root/
├── docker-compose.yml
├── Dockerfile
├── main.py
├── config.json                    # 📝 Configuración (volumen)
├── processed_messages.json        # 📊 Estado (volumen)
├── logs/                          # 📂 Volumen
│   └── gateway.log               # ← ACCESIBLE DESDE HOST
├── data/                          # 📂 Volumen (futuro)
└── venv/
```

---

## 🔄 PERSISTENCIA

### ✅ QUÉ PERSISTE

- ✓ `gateway.log` - Logs de la aplicación
- ✓ `config.json` - Cookies + webhook URL
- ✓ `processed_messages.json` - IDs de mensajes ya sincronizados

### ❌ QUÉ NO PERSISTE (se pierde al eliminar contenedor)

- ✗ Imagen Docker
- ✗ Código Python (está en imagen)
- ✗ Dependencias instaladas

### ✅ QUÉ PERSISTE SI USAS VOLUMES

Todo lo anterior persiste porque está en volúmenes del host.

---

## 🛠️ CASOS DE USO

### Caso 1: Revisar logs
```bash
tail -f logs/gateway.log
```

### Caso 2: Actualizar configuración
```bash
# El contenedor automáticamente detecta cambios
vim config.json

# Reiniciar contenedor (opcional)
docker-compose restart
```

### Caso 3: Backup de configuración
```bash
# Copiar fuera del contenedor (ya están en host!)
cp config.json config.json.backup
cp processed_messages.json processed_messages.json.backup
```

### Caso 4: Eliminar contenedor pero mantener datos
```bash
# Los datos persisten en host
docker-compose down

# El contenedor se elimina, pero los archivos quedan
ls -la logs/
ls -la config.json
```

### Caso 5: Reiniciar con misma configuración
```bash
docker-compose up -d

# Lee automáticamente config.json del host
# Conoce qué mensajes ya procesó (processed_messages.json)
```

---

## 🔐 PERMISOS

Docker Compose usa `user: root` para asegurar que:
- ✓ El contenedor puede escribir en volúmenes
- ✓ Los logs son accesibles desde host
- ✓ La configuración se puede actualizar

---

## 📋 MONITOREO

### Ver qué está en los volúmenes

```bash
# Logs actuales
ls -la logs/
wc -l logs/gateway.log

# Configuración
cat config.json | jq .

# Mensajes procesados
cat processed_messages.json | jq . | head -20
```

### Limpiar logs (opcional)

```bash
# Ver tamaño
du -sh logs/

# Limpiar
> logs/gateway.log

# O con Docker
docker exec linkedin-n8n-gateway truncate -s 0 /app/logs/gateway.log
```

---

## ⚠️ CONSIDERACIONES

### Si cambias permisos de archivos
```bash
# Volver a permisos correctos
chmod 644 config.json
chmod 644 processed_messages.json
```

### Si quieres volúmenes nombrados (en lugar de directorios)

```yaml
volumes:
  - linkedin-config:/app/config
  - linkedin-logs:/app/logs

volumes:
  linkedin-config:
  linkedin-logs:
```

Esto crea volúmenes en `/var/lib/docker/volumes/` (menos común).

---

## 🎯 RESUMEN

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| Logs accesibles | ❌ Dentro del contenedor | ✅ `./logs/` del host |
| Config persistente | ⚠️ Dentro del contenedor | ✅ `./config.json` del host |
| Estado sincronizado | ⚠️ Dentro del contenedor | ✅ `./processed_messages.json` |
| Eliminar contenedor | 📛 Se pierden datos | ✅ Datos persisten en host |
| Backup fácil | ❌ Complejidad | ✅ `cp` simple |
| Múltiples instancias | ❌ Comparten estado | ✅ Diferentes volúmenes |

---

**✅ Volúmenes configurados y listos para usar.**
