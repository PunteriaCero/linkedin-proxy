# Docker Guide

## 🐳 Build Local

### Build imagen

```bash
docker build -t linkedin-gateway:latest .
```

### Run contenedor

```bash
docker run -p 8000:8000 linkedin-gateway:latest
```

### Con volúmenes (para persistencia)

```bash
docker run -p 8000:8000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/logs:/app/logs \
  linkedin-gateway:latest
```

---

## 🚀 Docker Compose (Recomendado)

### Iniciar

```bash
docker-compose up -d
```

### Ver logs

```bash
docker-compose logs -f linkedin-gateway
```

### Detener

```bash
docker-compose down
```

### Rebuild

```bash
docker-compose up -d --build
```

---

## 🐳 GitHub Container Registry (GHCR)

Las imágenes se generan automáticamente en cada push/tag:

```
ghcr.io/punteriaczero/linkedin-proxy:master
ghcr.io/punteriaczero/linkedin-proxy:v1.0.0
ghcr.io/punteriaczero/linkedin-proxy:sha-abc1234
```

### Pull imagen

```bash
docker pull ghcr.io/punteriaczero/linkedin-proxy:master
```

### Run desde GHCR

```bash
docker run -p 8000:8000 \
  ghcr.io/punteriaczero/linkedin-proxy:master
```

---

## 🔐 Autenticación GHCR

Si la imagen es privada:

```bash
# Login
echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u USERNAME --password-stdin

# Pull
docker pull ghcr.io/punteriaczero/linkedin-proxy:master

# Logout
docker logout ghcr.io
```

---

## 📊 Verificar imagen

### Listar imágenes

```bash
docker images | grep linkedin
```

### Inspeccionar

```bash
docker inspect linkedin-gateway:latest
```

### Health check

```bash
docker run --rm linkedin-gateway:latest \
  curl http://localhost:8000/health
```

---

## 🔄 CI/CD Automático

El workflow `.github/workflows/docker.yml`:

1. ✅ Se ejecuta en cada **push** a main/master
2. ✅ Se ejecuta en cada **tag** de versión (v1.0.0)
3. ✅ Se puede ejecutar **manualmente**

### Ejecución manual

1. Ve a **Actions** → **Build and Push Docker Image**
2. Click en **Run workflow**
3. Selecciona rama
4. Espera resultado

---

## 📝 Versioning

### Tags automáticos

- `master` → última versión en master
- `v1.0.0` → versión específica (crea tag en git)
- `sha-abc1234` → commit específico

### Crear versión

```bash
# Crear tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push tag a GitHub
git push origin v1.0.0

# GitHub Actions automáticamente construye la imagen
```

---

## 🐳 Ejecutar en Producción

### Con Docker

```bash
docker run -d \
  --name linkedin-gateway \
  --restart always \
  -p 18791:8000 \
  -e PYTHONUNBUFFERED=1 \
  ghcr.io/punteriaczero/linkedin-proxy:v1.0.0
```

### Con Docker Compose

```bash
docker-compose -f docker-compose.yml up -d
```

### Con Systemd + Docker

```ini
[Unit]
Description=LinkedIn Gateway Docker
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/docker run --rm \
  --name linkedin-gateway \
  -p 18791:8000 \
  ghcr.io/punteriaczero/linkedin-proxy:latest

[Install]
WantedBy=multi-user.target
```

---

## 🔍 Debugging

### Ver logs del contenedor

```bash
docker logs -f linkedin-gateway
```

### Ejecutar bash

```bash
docker run -it linkedin-gateway:latest /bin/bash
```

### Ver ports

```bash
docker port linkedin-gateway
```

---

## 📊 Estadísticas

### Tamaño

```bash
docker images linkedin-gateway
```

### Uso de recursos

```bash
docker stats linkedin-gateway
```

---

¡Listo! Las imágenes se generan automáticamente. 🚀
