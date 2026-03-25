# Contribuyendo

¡Gracias por tu interés en contribuir a LinkedIn-n8n Gateway!

## Proceso

1. **Fork** el repositorio
2. **Crea una rama** para tu feature (`git checkout -b feature/amazing-feature`)
3. **Haz cambios** y asegúrate de que los tests pasen
4. **Commit** (`git commit -m 'Add amazing feature'`)
5. **Push** a tu rama (`git push origin feature/amazing-feature`)
6. **Abre un Pull Request**

## Requisitos

- Python 3.11+
- Todos los tests deben pasar (`python3 test_gateway.py`)
- Código debe seguir PEP 8
- Documenta cambios en README.md si es necesario

## Testing

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
python3 test_gateway.py

# Verificar cobertura
python3 -m pytest test_gateway.py --cov
```

## Reportar Bugs

Abre un issue con:
- Descripción clara del problema
- Pasos para reproducir
- Versión de Python
- Sistema operativo

## Sugerencias

¡Estamos abiertos a mejoras! Abre un discussion o issue para sugerir features.

---

Gracias por contribuir! 🎉
