# Drivly

Marketplace de reservas anticipadas de estacionamiento en Buenos Aires. Trabajo Final de Carrera de la Escuela Da Vinci.

| Parte | Carpeta | Quién la usa |
|---|---|---|
| API REST (Django, DRF, PostgreSQL, Celery) | raíz del repo | La app y el portal |
| App Android (Kotlin, Jetpack Compose) | `android/` | Conductores y playeros |
| Web (React, Vite, Material UI) | `frontend/` | Landing pública en `/` y panel de los administradores en `/panel` |

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

Sin Celery no se marcan los holds vencidos como expirados, no se reintentan los reembolsos ni los comprobantes, y no salen los recordatorios (de inicio, de fin y de deuda).

Si Mercado Pago no responde al pagar, la API devuelve 503 `PAGOS_NO_DISPONIBLES` y la app ofrece reintentar o ir al
garaje y pagar ahí (el lugar retenido se libera). Cada 10 minutos Celery concilia los pagos: busca en Mercado Pago
los checkouts de las últimas 24 h sin pago registrado y procesa los aprobados como si hubiera llegado el webhook
(confirma la reserva, salda la deuda o reembolsa si ya no hay lugar).

## Emails y notificaciones push

Los comprobantes (con el QR de la reserva), la activación de cuentas, los recordatorios de deuda y el formulario
"Sumá tu garaje" salen por email. Sin `EMAIL_HOST` en el `.env` se imprimen en la consola. Con Gmail se usa una
contraseña de aplicación; el formulario de la landing llega a `CONTACTO_EMAIL`.

Los push usan Firebase Cloud Messaging: `FCM_PROJECT_ID` en el `.env` y la clave de la cuenta de servicio en
`firebase-cuenta-servicio.json` (en la raíz, fuera del repo). La app toma los datos de Firebase de
`android/local.properties` (ver [docs/app-android.md](docs/app-android.md)). Sin esa configuración todo funciona igual, sin push.

## Web


```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173 (landing) y /panel (administradores)
```

El logo original y los diseños de la landing están en `branding/`; en `frontend/public/` van las versiones livianas.

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

El despliegue en producción está pendiente. Las fotos de los modelos de auto salen de un servicio no documentado
(carapi.trustcar.info): para producción conviene guardarlas en el servidor. Para buscar la foto de los autos ya cargados,
sin gastar consultas de DataCar: `python manage.py buscar_fotos`. La categoría del vehículo sale de DataCar (`DATACAR_MOCK=False` y `DATACAR_API_KEY`); en desarrollo conviene el simulador (`DATACAR_MOCK=True`), que no gasta saldo.
