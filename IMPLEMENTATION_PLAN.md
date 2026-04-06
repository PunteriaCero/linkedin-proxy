# 🔄 Mejoras a LinkedIn API - Plan de Implementación

**Objetivo:** Mantener conexión estable con LinkedIn para sincronización en tiempo real

## 📋 Plan de Trabajo

### FASE 1: WebSocket Connection Manager (2-3h)
1. Crear ConnectionManager para mantener clientes WebSocket conectados
2. Implementar /ws/messages endpoint para streaming de mensajes
3. Auto-reconnect con exponential backoff
4. Heartbeat para detectar desconexiones

### FASE 2: Real-time Message Polling (1-2h)
1. Reemplazar polling manual con AsyncIO tasks
2. Implementar background task que monitorea conversaciones
3. Notificar via WebSocket cuando hay mensajes nuevos
4. Configurar intervalo de polling (default: 30s)

### FASE 3: Conversation History Caching (1-2h)
1. Cache en-memory de conversaciones recientes
2. Invalidación automática (TTL: 5 minutos)
3. Endpoint /conversations con datos en caché
4. Endpoint /conversations/{id}/messages para historial

### FASE 4: Testing & Validation (2-3h)
1. Unit tests para ConnectionManager
2. Integration tests con simulación de LinkedIn
3. Load testing (múltiples clientes WebSocket)
4. Validación de estabilidad (24h test)

### FASE 5: Production Deployment (1h)
1. Configuración de Systemd
2. Docker setup con health checks
3. Documentación completa
4. Rollback strategy

## 🎯 Criterios de Éxito

- ✅ WebSocket conecta y reconecta automáticamente
- ✅ Mensajes nuevos llegan en <2s (latencia baja)
- ✅ Puede mantener 10+ conexiones simultáneas
- ✅ 99.5% uptime en test de 24h
- ✅ Manejo correcto de cookies expiradas
- ✅ Zero message loss

## 📊 Arquitectura Propuesta

```
Client (n8n)
    ↓
WebSocket /ws/messages
    ↓
ConnectionManager
    ↓
BackgroundTask: monitor_linkedin_messages()
    ↓
LinkedIn API (con retry logic)
    ↓
Cache: conversaciones recientes
    ↓
Mensaje nuevo → broadcast a todos los clientes WebSocket
```

## 🔧 Cambios a main.py

1. **Imports nuevos:**
   - `from fastapi import WebSocket, WebSocketDisconnect`
   - `from contextlib import asynccontextmanager`
   - `from collections import defaultdict`

2. **Nuevas clases:**
   - `ConnectionManager` - Maneja clientes WebSocket
   - `ConversationCache` - Cache con TTL
   - `MessageMonitor` - Background task

3. **Nuevos endpoints:**
   - `GET /ws/messages` - WebSocket para streaming
   - `GET /conversations` - Lista con caché
   - `GET /conversations/{id}/messages` - Historial

4. **Background tasks:**
   - `startup_event()` - Inicia monitor
   - `shutdown_event()` - Limpia conexiones
   - `monitor_linkedin_messages()` - Loop principal

## 🚀 Timeline

Fase 1-2: Hoy (3-5h)
Fase 3: Mañana (1-2h)
Fase 4-5: Día siguiente (3-4h)

**Total: 9-16h para full implementation**
