# Drivly

Marketplace de reservas anticipadas de estacionamiento en Buenos Aires. Trabajo Final de Carrera de la Escuela Da Vinci.

| Parte | Carpeta | Quién la usa |
|---|---|---|
| API REST (Django, DRF, PostgreSQL, Celery) | raíz del repo | La app y el portal |
| App Android (Kotlin, Jetpack Compose) | `android/` | Conductores y playeros |
| Portal web (React, Vite, Material UI) | `frontend/` | Administradores de garajes |

## Levantar el entorno de desarrollo

Hace falta Python, Node, Docker y, para la app, Android Studio.

```bash
docker compose up -d                  # PostgreSQL y Redis
python -m venv venv
venv\Scripts\activate                 # en Linux o macOS: source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                  # completar SECRET_KEY y las claves que se vayan a usar
python manage.py migrate
python manage.py seed_dev             # datos de prueba
python manage.py runserver
```

En otras dos terminales, para que corran las tareas programadas:

```bash
celery -A backend worker -l info --pool=solo   # en Windows hace falta --pool=solo
celery -A backend beat -l info
```

Celery necesita Redis (lo levanta `docker compose up -d`). Después de cambiar el `.env` hay que reiniciar Django y
los dos procesos de Celery: con Ctrl+C en cada terminal y volviendo a correr el comando.

Sin Celery no se marcan los holds vencidos como expirados, no se reintentan los reembolsos y no salen los recordatorios de deuda.

El portal web:

```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

La app se abre desde `android/` con Android Studio. Su configuración local está en [docs/app-android.md](docs/app-android.md).

## Tests

```bash
python -m pytest                      # backend: necesita PostgreSQL
cd android && ./gradlew :app:testDebugUnitTest
cd frontend && npm run build
```

## Documentación

- [docs/app-android.md](docs/app-android.md): contrato de la app con la API, pagos y configuración.
- [frontend/README.md](frontend/README.md): portal web, tema y endpoints que usa.
- La documentación de tesis (`.docx`) se guarda en `docs/` y no se sube al repositorio.

## Estado

El despliegue en producción está pendiente. La categoría del vehículo sale de DataCar (`DATACAR_MOCK=False` y `DATACAR_API_KEY`); en desarrollo conviene el simulador (`DATACAR_MOCK=True`), que no gasta saldo.
