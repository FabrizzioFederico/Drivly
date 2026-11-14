# Drivly Web (React + Vite + Material UI)

Dos partes en la misma app, según la ruta (`src/App.jsx`):

- `/`: landing pública (`src/views/LandingView.jsx`) para conductores y garajes, con las slides de los diseños y el
  formulario "Sumá tu garaje" (`POST /notificaciones/contacto/`).
- `/panel`: portal de los administradores de garajes, conectado a la API REST de Django (DRF) con JWT. Conductores y
  playeros usan la app Android (carpeta `android/`): acá no pueden iniciar sesión.

En computadora el menú del panel es una barra de íconos fija (el nombre aparece al pasar el mouse); en el celular, una
hamburguesa. El monitor y las deudas se actualizan solos cada 5 s (`src/lib/useEnVivo.js`) y el gráfico de ocupación
usa Chart.js. El logo está en `src/components/LogoDrivly.jsx` (archivo: `public/logo-drivly.png`).

La interfaz usa Material Design con [MUI](https://mui.com/material-ui/). El tema oscuro y todos los colores están en `src/theme.js`, publicados como variables CSS (`var(--surface-2)`, `var(--accent)`, etc.), y cada sección del portal en `src/views/admin/`. No escribir colores sueltos en los componentes. MUI 9 ignora las system props en los componentes: los colores de texto van en `sx`, por ejemplo `sx={{ color: 'text.secondary' }}`.

## Inicio rápido

```bash
cp .env.example .env      # VITE_USE_MOCKS=true para correr sin backend
npm install
npm run dev               # http://localhost:5173 y http://localhost:5173/panel
```

Con `VITE_USE_MOCKS=false` las llamadas van a `VITE_API_URL`. Para evitar CORS en desarrollo podés usar `VITE_API_URL=/api` (proxy de Vite a `localhost:8000`) o configurar `django-cors-headers`.

## Autenticación

- `POST /auth/google/ { id_token, rol: 'ADMIN_GARAJE' }` → `{ access, refresh, user }`. El backend valida el ID token de Google y emite JWT (SimpleJWT). El rol sólo se usa al crear la cuenta: quien se registra en el portal es administrador.
- Para que el botón "Iniciar sesión con Google" funcione, el client ID web (`VITE_GOOGLE_CLIENT_ID`) tiene que tener
  cargados en Google Cloud Console > Credenciales > *Orígenes autorizados de JavaScript* `http://localhost:5173`,
  `http://localhost` y el dominio de ngrok (`https://...ngrok-free.dev`). Si falta, la consola del navegador muestra
  `The given origin is not allowed for the given client ID`. Una cuenta que ya es conductor en la app no entra al panel.
- Si la cuenta es de un conductor o un playero, el portal no guarda los tokens y le indica que use la app.
- `POST /auth/refresh/ { refresh }` → `{ access[, refresh] }`.
- `src/api/client.js` agrega `Authorization: Bearer <access>`, renueva el token una sola vez ante un 401 (las requests concurrentes esperan esa misma renovación) y emite `drivly:logout` si falla.
- Los errores de DRF (`detail` o errores por campo) se normalizan a `{ status, message, fields }`.

## Endpoints

Todos con barra final (convención de los routers de DRF).

| Servicio | Método y ruta | Uso |
|---|---|---|
| auth | `POST /auth/google/`, `POST /auth/refresh/`, `GET /auth/me/` | Login y perfil con `rol` |
| garajes | `GET /garajes/`, `GET/PATCH /garajes/{id}/` | `capacidad`, `cupo_abonos`, `salida_estimada_default_min`, `tolerancia_min`, `recargo_overstay` (CU-06) |
| garajes | `GET/PUT /garajes/{id}/tarifas/` | Filas `{ categoria, modalidad, precio_primera_hora, precio_fraccion, fraccion_min, minimo_fracciones, tope_12h, tope_24h, precio_periodo }` |
| garajes | `PUT/DELETE /garajes/{id}/foto/` | Foto del estacionamiento (multipart `foto`, hasta 8 MB, se guarda 1280×720); la ve el conductor en la app |
| garajes | `GET /garajes/{id}/resenas/?page`, `POST /garajes/{id}/resenas/{resena_id}/responder/` | Opiniones: promedio, cantidad por estrellas y comentarios; el admin responde (vacía la borra) |
| garajes | `GET /garajes/{id}/informe/?desde&hasta`, `GET /garajes/{id}/informe/pdf/` | Caja e informe: ingresos por medio, comisión y cierres de caja; el PDF se baja como archivo |
| garajes | `GET /garajes/{id}/ocupacion/`, `GET /garajes/{id}/metricas/` | Monitor, alertas de overstay y KPIs (CU-10) |
| garajes | `GET/POST /garajes/{id}/playeros/`, `DELETE /garajes/{id}/playeros/{usuario}/` | Equipo (RFW-06) |
| reservas | `GET /reservas/?garaje=` | Reservas del garaje |
| operación | `GET /operacion/deudas/?garaje=`, `POST /operacion/deudas/{id}/condonar/` | Deudas impagas y condonación |
| operación | `GET /operacion/cierres/?garaje=` | Cierres de caja de los playeros |
| notificaciones | `POST /notificaciones/contacto/` | Formulario de la landing (sin sesión, 5 por hora) |
| pagos | `GET /pagos/oauth/estado/?garaje=`, `POST /pagos/oauth/conectar/` | Conexión del garaje con Mercado Pago |

La API de la app está en `docs/app-android.md`.
