# GitHub Actions - Guía de Uso

## 📋 Qué es este Workflow

El archivo `.github/workflows/tests.yml` configura un **GitHub Action** que:

1. ✅ Ejecuta tests automáticamente en cada push
2. ✅ Ejecuta tests en Pull Requests
3. ✅ Permite ejecución manual desde la interfaz

## 🔄 Ejecuciones Automáticas

### En cada Push

Cuando pusheas cambios a `main` o `master`:

```bash
git push origin master
```

GitHub **automáticamente**:
1. Crea un runner (máquina virtual)
2. Clona el repo
3. Instala Python 3.11
4. Instala dependencias (`requirements.txt`)
5. Ejecuta `python3 test_gateway.py`
6. Reporta resultado (✅ o ❌)

### En Pull Requests

Cuando abres un PR, GitHub automáticamente ejecuta los tests para verificar que el código es válido.

## 🎯 Ejecutar Manualmente

### Opción 1: Desde GitHub Web

1. Ve a tu repo: https://github.com/PunteriaCero/linkedin-proxy
2. Click en pestaña **"Actions"**
3. Click en **"Tests"** (el workflow)
4. Click en **"Run workflow"** (botón verde a la derecha)
5. Selecciona rama: `master`
6. Click en **"Run workflow"**

### Opción 2: Desde CLI

```bash
# Ver workflows disponibles
gh workflow list

# Ejecutar el workflow "Tests" en main
gh workflow run tests.yml --ref main

# O en master
gh workflow run tests.yml --ref master
```

## 📊 Ver Resultados

### En GitHub Web

1. Ve a **Actions**
2. Haz click en el run más reciente
3. Expande **"Run tests"** para ver logs detallados

### Ver Logs Completos

Haz click en el job "test" para ver:
- Setup de Python
- Instalación de dependencias
- Output completo de tests
- Timestamps de cada paso

## 🔴 Si los Tests Fallan

### Pasos para Debuggear

1. **Ver los logs** en GitHub Actions
2. **Reproducir localmente**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 test_gateway.py
   ```
3. **Comparar output** local vs GitHub
4. **Pushear fixes** y rerun

### Rerun Fallido

Si un run falló y lo solucionaste:

```bash
git push origin master
```

O ejecuta manualmente desde Actions.

## 🛠️ Personalización

### Cambiar la Rama

Para ejecutar en una rama diferente, edita `.github/workflows/tests.yml`:

```yaml
on:
  push:
    branches: [ main, master, develop ]  # Agregar rama aquí
```

### Agregar Más Versiones de Python

```yaml
matrix:
  python-version: ['3.9', '3.10', '3.11', '3.12']
```

### Agregar Más Pasos

```yaml
- name: 📊 Code Coverage
  run: |
    pip install pytest-cov
    pytest test_gateway.py --cov=.
```

## ✅ Status Badge

El badge en el README (`[![Tests](...)...]`) muestra:
- 🟢 **Verde**: Última ejecución pasó
- 🔴 **Rojo**: Última ejecución falló
- ⚪ **Gris**: No hay ejecuciones aún

Click en el badge para ir directamente a Actions.

## 📝 Ejemplo Real

```
You (dev)
   ↓
git push origin master
   ↓
GitHub detecta push
   ↓
Ejecuta workflow "Tests"
   ↓
- Setup Python 3.11
- pip install -r requirements.txt
- python3 test_gateway.py
   ↓
Si ✅ → Merge permitido
Si ❌ → Mostrar error
```

## 🔗 Links Útiles

- Actions: https://github.com/PunteriaCero/linkedin-proxy/actions
- Workflow file: `.github/workflows/tests.yml`
- GitHub Actions Docs: https://docs.github.com/en/actions

## ❓ FAQs

**P: ¿Los tests se ejecutan siempre?**  
R: Sí, en cada push a main/master y en PRs.

**P: ¿Puedo deshabilitarlos?**  
R: Sí, elimina `.github/workflows/tests.yml` y haz commit.

**P: ¿Cuánto tarda?**  
R: ~30-60 segundos (setup + install + tests).

**P: ¿Me cuesta dinero?**  
R: No, GitHub incluye 2000 minutos/mes gratis.

---

¡Listo! Tus tests se ejecutan automáticamente ahora. 🚀
