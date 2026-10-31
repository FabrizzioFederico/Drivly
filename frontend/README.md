# Drivly Web (React + Vite + Tailwind)

Portal de los administradores de garajes, conectado a la API REST de Django (DRF) con JWT.
Conductores y playeros usan la app Android (carpeta `android/`): acá no pueden iniciar sesión.

## Inicio rápido

```bash
cp .env.example .env      # VITE_USE_MOCKS=true para correr sin backend
npm install
npm run dev               # http://localhost:5173
```

Con `VITE_USE_MOCKS=false` las llamadas van a `VITE_API_URL`. Para evitar CORS en desarrollo podés usar `VITE_API_URL=/api` (proxy de Vite a `localhost:8000`) o configurar `django-cors-headers`.

## Autenticación

- `POST /auth/google/ { id_token, rol: 'ADMIN_GARAJE' }` → `{ access, refresh, user }`. El backend valida el ID token de Google y emite JWT (SimpleJWT). El rol sólo se usa al crear la cuenta: quien se registra en el portal es administrador.
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
| garajes | `GET/PUT /garajes/{id}/tarifas/` | Filas `{ categoria, modalidad, precio_fraccion, fraccion_min, minimo_fracciones, precio_periodo }` |
| garajes | `GET /garajes/{id}/ocupacion/`, `GET /garajes/{id}/metricas/` | Monitor, alertas de overstay y KPIs (CU-10) |
| garajes | `GET/POST /garajes/{id}/playeros/`, `DELETE /garajes/{id}/playeros/{usuario}/` | Equipo (RFW-06) |
| reservas | `GET /reservas/?garaje=` | Reservas del garaje |
| operación | `GET /operacion/deudas/?garaje=`, `POST /operacion/deudas/{id}/condonar/` | Deudas impagas y condonación |
| pagos | `GET /pagos/oauth/estado/?garaje=`, `POST /pagos/oauth/conectar/` | Conexión del garaje con Mercado Pago |

La API de la app está en `docs/app-android.md`.
