# App Android del conductor — contrato con el backend

La app Kotlin (carpeta `android/`, a crear) usa la misma API que la vista web del conductor
(`frontend/src/views/DriverAppView.jsx`), que queda como referencia y para pruebas.

## Configuración local

En `android/local.properties` (no se sube al repo):

```properties
drivly.apiUrl=https://<dominio-ngrok>/api/
drivly.googleWebClientId=<el mismo client ID web que VITE_GOOGLE_CLIENT_ID>
```

Para "Ingresar con Google" hay que crear además un **client ID de tipo Android** en Google Cloud Console
(mismo proyecto que el web) con el paquete `com.drivly.app` y el SHA-1 del certificado
(`./gradlew :app:signingReport`). La app pide el token con el client ID **web**, que es el que valida el backend.

## Base URL

| Entorno | URL |
|---|---|
| Desarrollo con Mercado Pago | `https://<dominio-ngrok>/api/` (ngrok → Vite :5173 → Django) |
| Emulador sin Mercado Pago | `http://10.0.2.2:8000/api/` — agregar `10.0.2.2` a `ALLOWED_HOSTS` y permitir tráfico HTTP en debug |

## Autenticación (JWT)

| Método | Ruta | Body | Respuesta |
|---|---|---|---|
| POST | `auth/google/` | `{ "id_token": "<Credential Manager>" }` | `{ access, refresh, user }` — crea la cuenta como CONDUCTOR |
| POST | `auth/dev-login/` | `{ "rol": "CONDUCTOR" }` | igual (sólo con `DEBUG=True`) |
| POST | `auth/refresh/` | `{ "refresh": "..." }` | `{ access, refresh }` — el refresh rota: guardar el nuevo |
| GET | `auth/me/` | — | usuario logueado |

- Header: `Authorization: Bearer <access>`. El access dura 15 min y el refresh 7 días.
- El client ID de Android tiene que estar en `GOOGLE_OAUTH_CLIENT_IDS` del backend (separado por comas, junto al web).

## Endpoints del conductor

| Método | Ruta | Uso |
|---|---|---|
| GET/POST | `vehiculos/` | Listar / registrar patente (la categoría sale de DataCar, no se elige) |
| POST | `vehiculos/{id}/declarar/` | `{ "categoria": "AUTO" \| "CAMIONETA" }` si DataCar no respondió |
| GET | `garajes/disponibles/?lat&lng&radio&inicio&fin&modalidad` | Búsqueda (sólo garajes que pueden cobrar) |
| GET | `garajes/{id}/cercanos/?inicio&fin&modalidad` | Alternativas si el garaje está lleno |
| GET | `reservas/cotizar/?garaje&vehiculo&modalidad&inicio&fin` | Precio estimado sin retener el lugar (`total`, `fracciones`, `precio_fraccion`) |
| POST | `reservas/hold/` | `{ garaje, vehiculo, modalidad, inicio, fin? }` → retiene el lugar 5 min |
| POST | `reservas/{id}/pagar/` | `{ "canal": "app" }` → `{ init_point }` |
| GET | `reservas/{id}/` | Estado de la reserva (`HOLD`, `CONFIRMADA`, …) y `cancelable_hasta` |
| GET | `reservas/{id}/qr/` | `{ qr_token, valido_desde, valido_hasta, reutilizable }` |
| POST | `reservas/{id}/cancelar/` | Cancela; `reembolso`: `REEMBOLSADO`, `REEMBOLSO_FALLIDO` (se reintenta solo) o `null` |
| GET | `reservas/` | Mis reservas (paginado: `results`) |

Las fechas van en ISO 8601 con zona horaria. Los errores de negocio responden `{ "detail", "code" }`
(por ejemplo `SIN_CUPO` con `cercanos`, `GARAJE_SIN_MERCADO_PAGO`, `DEUDA_PENDIENTE`, `ESTADO_INVALIDO`):
la app decide qué mostrar según `code`.

## Pago con Mercado Pago (Checkout Pro mobile)

1. `POST reservas/{id}/pagar/` con `{ "canal": "app" }`. Nunca mandar montos: el backend usa el monto congelado.
2. Abrir `init_point` en una **Custom Tab** (`androidx.browser:browser`):
   ```kotlin
   CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(initPoint))
   ```
3. Al terminar, Mercado Pago redirige a `drivly://pago-resultado?mp_status=success&collection_status=approved&external_reference=<reserva_id>&payment_id=...`
   y la Custom Tab se cierra sola. Declarar la Activity en `AndroidManifest.xml`:
   ```xml
   <activity android:name=".PagoResultadoActivity" android:exported="true">
       <intent-filter>
           <action android:name="android.intent.action.VIEW" />
           <category android:name="android.intent.category.DEFAULT" />
           <category android:name="android.intent.category.BROWSABLE" />
           <data android:scheme="drivly" android:host="pago-resultado" />
       </intent-filter>
   </activity>
   ```
4. **No confiar en los parámetros del deep link.** Con `collection_status=approved`, consultar
   `GET reservas/{external_reference}/` cada 2 s (hasta ~30 s) hasta que el estado sea `CONFIRMADA`:
   lo confirma el webhook en el servidor. Mismo criterio que `DriverAppView.jsx`.
5. Si el conductor cierra la Custom Tab sin pagar no llega ningún deep link: al volver a la app, consultar la reserva.

El scheme se cambia con `APP_DEEPLINK_PAGO` en el `.env` del backend (default `drivly://pago-resultado`).

## Ticket y QR sin señal

Descargar `reservas/{id}/qr/` una vez y guardarlo (Room o DataStore): el token está firmado y sirve sin conexión.
Renderizarlo como QR (por ejemplo con ZXing). Si la reserva se cancela, borrar el QR guardado.

## Cancelación

Mostrar "Cancelar reserva" sólo mientras `now <= cancelable_hasta` (2 h antes del inicio, o 10 min después de pagar).
El servidor vuelve a validar el plazo: si vence entre medio, responde 409 `ESTADO_INVALIDO`.

## Pruebas

Usar las cuentas de prueba de Mercado Pago: **Comprador** para pagar desde la app, **Vendedor** para el garaje
(conectado desde el portal web del admin) y **Marketplace** como dueña de la app de pruebas.
