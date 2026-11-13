# App Android — contrato con el backend

La app Kotlin (carpeta `android/`) es el único cliente de conductores y playeros.
La web (`frontend/`) tiene la landing pública (`/`) y el portal de los administradores (`/panel`).

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
| POST | `auth/google/` | `{ "id_token": "<Credential Manager>" }` | `{ access, refresh, user }` — crea la cuenta como CONDUCTOR. Si la cuenta no tiene foto, copia la de Google (512 px) |
| POST | `auth/registro/` | `{ nombre, email, password }` | 201 `{ detail, email, email_enviado }`: la cuenta (siempre CONDUCTOR) queda sin activar y llega un email con el link |
| POST | `auth/activar/reenviar/` | `{ email }` | 202 siempre (no revela si la cuenta existe); manda otro link si está pendiente |
| GET | `auth/activar/{uid}/{token}/` | — | El link del email: página HTML de "cuenta activada" con el botón `drivly://cuenta-activada`. Vence a los 3 días |
| POST | `auth/login/` | `{ email, password }` | `{ access, refresh, user }`; 401 `CREDENCIALES_INVALIDAS` si no coinciden; 403 `CUENTA_SIN_ACTIVAR` si falta el link |
| POST | `auth/dev-login/` | `{ "rol": "CONDUCTOR" }` | igual (sólo con `DEBUG=True`) |
| POST | `auth/refresh/` | `{ "refresh": "..." }` | `{ access, refresh }` — el refresh rota: guardar el nuevo |
| GET/PATCH | `auth/me/` | `{ nombre?, genero?, telefono? }` | usuario logueado (`foto` es una ruta relativa: `/api/media/...`) |
| PUT/DELETE | `auth/me/foto/` | multipart `foto` (JPG/PNG/WebP, máx. 5 MB) | la reemplaza (se guarda 512×512) / la quita |
| POST | `auth/me/email/` | `{ email }` | manda un código de 6 dígitos al email nuevo (202) |
| POST | `auth/me/email/confirmar/` | `{ codigo }` | aplica el cambio; vence en 15 min y admite 5 intentos |

- Header: `Authorization: Bearer <access>`. El access dura 15 min y el refresh 7 días.
- Registro y login con contraseña admiten 10 intentos por minuto por IP (después responden 429).
- Para pasar una cuenta a playero, el admin carga su email en Equipo (portal web). Al abrirse, la app consulta
  `auth/me/` y actualiza el rol guardado. Si una cuenta con contraseña entra después con Google, la contraseña
  deja de valer: el registro no verifica el email y así se evita que alguien se adueñe de un email ajeno.
- El client ID de Android tiene que estar en `GOOGLE_OAUTH_CLIENT_IDS` del backend (separado por comas, junto al web).

## Endpoints del conductor

| Método | Ruta | Uso |
|---|---|---|
| GET/POST | `vehiculos/` | Listar / registrar patente (la categoría sale de DataCar, no se elige). Incluye `marca`, `modelo`, `anio` y `tipo` de DataCar |
| POST | `vehiculos/{id}/declarar/` | `{ "categoria": "CAMIONETA" }` si DataCar no la resolvió. "Auto" sólo sale de DataCar: así nadie paga como auto con una camioneta |
| POST | `vehiculos/{id}/revalidar/` | Vuelve a consultar DataCar |
| GET | `garajes/disponibles/?lat&lng&radio&inicio&fin&modalidad` | Búsqueda (sólo garajes que pueden cobrar). `foto` es la ruta de la foto del frente (`/api/media/...`) o `null`; también viene en `garaje_detalle` de la reserva |
| GET | `garajes/{id}/cercanos/?inicio&fin&modalidad` | Alternativas si el garaje está lleno |
| GET | `reservas/cotizar/?garaje&vehiculo&modalidad&inicio&fin` | Precio estimado sin retener el lugar (`total`, `fracciones`, `precio_fraccion`, `precio_primera_hora`; `tope_aplicado` = `12h`/`24h` si se cobró la estadía, con `sin_tope`) |
| POST | `reservas/hold/` | `{ garaje, vehiculo, modalidad, inicio, fin? }` → retiene el lugar 5 min |
| POST | `reservas/{id}/pagar/` | `{ "canal": "app" }` → `{ init_point }` |
| GET | `reservas/{id}/` | Estado de la reserva (`HOLD`, `CONFIRMADA`, …) y `cancelable_hasta` |
| GET | `reservas/{id}/qr/` | `{ qr_token, valido_desde, valido_hasta, reutilizable }` |
| POST | `reservas/{id}/cancelar/` | Cancela; `reembolso`: `REEMBOLSADO`, `REEMBOLSO_FALLIDO` (se reintenta solo) o `null` |
| GET | `reservas/` | Mis reservas (paginado: `results`) |
| GET | `operacion/mis-deudas/` | Deudas pendientes del conductor (lista sin paginar) |
| POST | `operacion/mis-deudas/{reserva_id}/pagar/` | `{ "canal": "app" }` → `{ init_point }`; vuelve con `external_reference=deuda:<reserva_id>` |

### Abonos

Se usan los mismos endpoints que una reserva por hora, con `modalidad` en `SEMANAL`, `MENSUAL` o `ANUAL` en
`garajes/disponibles/`, `reservas/cotizar/` y `reservas/hold/`. El fin definitivo lo calcula el backend: el que manda la app
sólo sirve para buscar. El QR se reutiliza en cada ingreso y egreso hasta que vence el abono.

## Endpoints del playero

Con rol `PLAYERO` la app abre `ui/playero/PlayeroScreen.kt`.

| Método | Ruta | Uso |
|---|---|---|
| GET | `garajes/` | El garaje del playero (paginado; vacío si no tiene uno asignado) |
| GET | `garajes/{id}/ocupacion/` | Semáforo y `alertas_overstay`; se consulta cada 10 s |
| GET | `garajes/{id}/cercanos/` | Garajes a los que derivar |
| POST | `operacion/ingreso/` | `{ garaje, qr_token }` o `{ garaje, patente, salida_estimada }` |
| POST | `operacion/egreso/` | `{ garaje, qr_token \| patente }` → `{ reserva, deuda, ocupacion }` |
| POST | `operacion/sin-lugar/` | `{ garaje, qr_token }` → `{ reserva, reembolso, cercanos }` |
| GET | `operacion/deudas/{reserva_id}/` | `{ pagado, transaccion_id }`; se consulta cada 3 s mientras se muestra el QR |
| POST | `operacion/deudas/{reserva_id}/efectivo/` | Registra el cobro en efectivo |
| POST | `operacion/presencial/{reserva_id}/medio/` | `{ garaje, medio }` con `EFECTIVO`, `MERCADO_PAGO` o `TRANSFERENCIA`: cómo pagó el cliente sin reserva al salir. Se puede corregir hasta que entra en un cierre (409 después) |
| GET | `operacion/caja/?garaje=` | Lo cobrado desde el último cierre: `efectivo_esperado`, `presenciales` y `excesos` por medio (`SIN_INDICAR` cuenta como efectivo), `app` y `ultimo_cierre` |
| POST | `operacion/caja/cerrar/` | `{ garaje, efectivo_contado, observaciones? }` → el cierre con `diferencia` (contado − esperado; negativa es faltante) |

Las fechas van en ISO 8601 con zona horaria. Los errores de negocio responden `{ "detail", "code" }`
(por ejemplo `SIN_CUPO` con `cercanos`, `GARAJE_SIN_MERCADO_PAGO`, `DEUDA_PENDIENTE`, `ESTADO_INVALIDO`,
`DEUDA_PATENTE` con `deuda`, `SIN_LUGAR_PRESENCIAL` con `cercanos`):
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
   lo confirma el webhook en el servidor.
5. Si el conductor cierra la Custom Tab sin pagar no llega ningún deep link: al volver a la app, consultar la reserva.

El scheme se cambia con `APP_DEEPLINK_PAGO` en el `.env` del backend (default `drivly://pago-resultado`).

## Ticket y QR sin señal

Descargar `reservas/{id}/qr/` una vez y guardarlo (Room o DataStore): el token está firmado y sirve sin conexión.
Renderizarlo como QR (por ejemplo con ZXing). Si la reserva se cancela, borrar el QR guardado.

## Cancelación

Mostrar "Cancelar reserva" sólo mientras `now <= cancelable_hasta` (2 h antes del inicio, o 10 min después de pagar).
El servidor vuelve a validar el plazo: si vence entre medio, responde 409 `ESTADO_INVALIDO`.

## Notificaciones push

Usan Firebase Cloud Messaging sin `google-services.json`: la app se configura desde `local.properties`
(Firebase > Configuración del proyecto > tu app Android con el paquete `com.drivly.app`):

```properties
drivly.firebaseProjectId=<ID del proyecto>
drivly.firebaseAppId=<ID de la app, 1:...:android:...>
drivly.firebaseApiKey=<clave de API web>
drivly.firebaseSenderId=<número del remitente>
```

Sin esos datos la app funciona igual, sin push. Al ingresar pide el permiso de notificaciones (Android 13+) y registra
el token con `POST notificaciones/dispositivos/ { token }`; al cerrar sesión lo borra con `DELETE` y el mismo cuerpo.
Al tocar un aviso se abre el ticket (`tipo=reserva`) o Mis reservas (`tipo=deuda`).

El backend manda: reserva confirmada, recordatorio 30 min antes del inicio, aviso 15 min antes del fin, deuda saldada,
reembolso y los recordatorios de deuda. Necesita `FCM_PROJECT_ID` y `FCM_CREDENCIALES` (JSON de la cuenta de servicio)
en el `.env`. Los comprobantes de pago, deuda y reembolso salen además por email.

## Cámara del playero

La pantalla del playero pide el permiso `CAMERA` recién al elegir qué va a escanear. El visor usa CameraX y ML Kit, con el modelo
incluido en la app. Sin permiso o sin cámara, se puede cargar la patente o el código a mano.

## Pruebas

Usar las cuentas de prueba de Mercado Pago: **Comprador** para pagar desde la app, **Vendedor** para el garaje
(conectado desde el portal web del admin) y **Marketplace** como dueña de la app de pruebas.
