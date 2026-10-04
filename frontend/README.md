# Drivly Web (React + Vite + Tailwind)

Cliente web de Drivly conectado a la API REST de Django (DRF) con JWT.

## Inicio rápido

```bash
cp .env.example .env      # VITE_USE_MOCKS=true para correr sin backend
npm install
npm run dev               # http://localhost:5173
```

Con `VITE_USE_MOCKS=false` las llamadas van a `VITE_API_URL`. Para evitar CORS en desarrollo podés usar `VITE_API_URL=/api` (proxy de Vite a `localhost:8000`) o configurar `django-cors-headers`.

## Autenticación

- `POST /auth/google/ { id_token }` → `{ access, refresh, user }`. El backend valida el ID token de Google y emite JWT (SimpleJWT).
- `POST /auth/refresh/ { refresh }` → `{ access[, refresh] }`.
- `src/api/client.js` agrega `Authorization: Bearer <access>`, renueva el token una sola vez ante un 401 (las requests concurrentes esperan esa misma renovación) y emite `drivly:logout` si falla.
- Los errores de DRF (`detail` o errores por campo) se normalizan a `{ status, message, fields }`.

## Endpoints

Todos con barra final (convención de los routers de DRF).

| Servicio | Método y ruta | Uso |
|---|---|---|
| auth | `POST /auth/google/`, `POST /auth/refresh/`, `GET /auth/me/` | Login y perfil con `rol` y `garaje` |
| vehículos | `GET /vehiculos/`, `POST /vehiculos/ { patente }`, `POST /vehiculos/{id}/revalidar/` | La categoría la asigna el backend con patente.ar (regla 3) |
| garajes | `GET /garajes/disponibles/?lat&lng&radio&inicio&fin&modalidad` | Búsqueda; sólo garajes que ofrecen esa modalidad |
| garajes | `GET /garajes/{id}/cercanos/?inicio&fin&modalidad`* | Garajes con lugar cerca de uno lleno (regla 6) |
| garajes | `GET /garajes/{id}/`, `PATCH /garajes/{id}/` | `capacidad`, `cupo_abonos`, `salida_estimada_default_min`, `tolerancia_min`, `recargo_overstay` (CU-06) |
| garajes | `GET/PUT /garajes/{id}/tarifas/`* | Filas `{ categoria, modalidad, precio_fraccion, fraccion_min, minimo_fracciones, precio_periodo }` |
| garajes | `GET /garajes/{id}/ocupacion/`*, `GET /garajes/{id}/metricas/`* | Semáforo con `libres_presencial`, timeline y KPIs (CU-10) |
| reservas | `GET /reservas/`, `GET /reservas/{id}/` | Listado con filtro `?estado=` |
| reservas | `POST /reservas/hold/ { garaje, vehiculo, modalidad, inicio, fin }` | Hold de 5 min. 409 `{ code: 'SIN_CUPO', cercanos }` sin lugar (CU-04) |
| reservas | `POST /reservas/{id}/cancelar/`, `POST /reservas/{id}/pagar/`* | Libera el Hold / pago |
| reservas | `GET /reservas/{id}/qr/`* | QR estático firmado, válido mientras la reserva esté vigente |
| operación | `POST /operacion/ingreso/` | `{ qr_token }` o `{ patente, salida_estimada }` (sin reserva). 409 `SIN_LUGAR_PRESENCIAL` con `cercanos` |
| operación | `POST /operacion/egreso/` | Puede devolver `deuda`; `recargo` es un porcentaje (0.5 = +50 %) |
| operación | `POST /operacion/sin-lugar/ { qr_token }`* | Reserva que llega sin lugar físico: reembolso + `cercanos` |
| operación | `GET /operacion/deudas/{id}/`*, `POST /operacion/deudas/{id}/efectivo/`* | Polling de Mercado Pago y cobro en efectivo |

\* Endpoints que todavía no existen en el backend. Las formas de respuesta están documentadas en cada servicio y reproducidas en `src/api/mocks.js`.

## Reglas de negocio que respeta el frontend

- **Regla 3 · categoría:** el conductor elige uno de sus vehículos validados; nunca la categoría. El Hold envía `vehiculo`, no `categoria`.
- **Regla 5 · abonos:** semanal, mensual y anual, en cochera móvil (sin lugar fijo). El admin define un máximo de lugares para abonos dentro de la capacidad.
- **Regla 6 · capacidad única:** app, abonos y presenciales comparten la capacidad. El semáforo del playero muestra cuántos clientes sin reserva pueden entrar sin dejar sin lugar a los conductores de la app que llegan en la ventana; en rojo no se registra el ingreso y se ofrecen garajes cercanos. Lo mismo cuando una reserva llega y no hay lugar físico, o cuando el conductor elige un garaje lleno.
- **QR:** estático y firmado por el servidor (HMAC). Se guarda en el teléfono y funciona sin señal (RFM-09). La seguridad viene de la firma, del estado de la reserva (sólo una CONFIRMADA habilita el ingreso) y de que el playero compara la patente.

## Notas

- **Hold timer:** se calcula contra `hold_expira_en` del servidor, no con un contador local, así sigue siendo correcto con la pestaña en segundo plano.
- **Ticket offline:** el QR se guarda en `localStorage` (`drivly.ticket.{id}`) y no vence. Para abrir la web sin señal también hace falta un service worker (por ejemplo, `vite-plugin-pwa`); en la app Kotlin se guarda localmente.
- **Escáner:** usa `BarcodeDetector` nativo (Chrome/Android). Sin soporte, el playero usa el campo manual. Para iOS más antiguo, reemplazar por `html5-qrcode`.
- **Mapa:** `DriverAppView` usa una proyección simple como marcador de posición. Reemplazar por `@vis.gl/react-google-maps` con un estilo oscuro.
- **Roles:** el selector de rol del header aparece solo en modo demo o para administradores. En producción, el rol sale de `/auth/me/`.
