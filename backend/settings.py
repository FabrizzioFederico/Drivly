"""
Configuración de Drivly (Django 6.1).
Todos los valores sensibles o que cambian por entorno se leen de variables de entorno (.env).
"""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# --- Seguridad -------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")  # sin default: si falta, el servidor no arranca
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Apps ------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # DateTimeRangeField (tstzrange) y GiST
    # Terceros
    "rest_framework",
    "corsheaders",
    # Drivly (crear con: python manage.py startapp <nombre>)
    "cuentas",
    "garajes",
    "vehiculos",
    "reservas",
    "pagos",
    "operacion",
    "reportes",
    "integraciones",
    "notificaciones",
]

# Usuario propio: definirlo ANTES de la primera migración del proyecto.
AUTH_USER_MODEL = "cuentas.Usuario"

# CorsMiddleware va primero (siempre antes de CommonMiddleware) y sin duplicados.
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Sirve los archivos estáticos (CSS y JS del admin de Django) con DEBUG=False, sin nginx
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Base de datos ---------------------------------------------------------
# PostgreSQL obligatorio: tstzrange, índices GiST y SELECT ... FOR UPDATE no existen en SQLite.
DATABASES = {"default": env.db("DATABASE_URL")}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Idioma y zona horaria -------------------------------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"  # sólo para mostrar
USE_I18N = True
USE_TZ = True  # la base guarda siempre UTC

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # lo llena `collectstatic` en el build de Render
# Fotos de perfil y de los garajes. Bajo /api/ para que pasen por el mismo proxy que la API (Vite en desarrollo, ngrok).
MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Con CLOUDINARY_URL las fotos van a Cloudinary (en Render el disco se borra en cada deploy); sin ella, a media/.
CLOUDINARY_URL = env("CLOUDINARY_URL", default="").strip()
if CLOUDINARY_URL and not CLOUDINARY_URL.startswith("cloudinary://"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "CLOUDINARY_URL tiene que ser la dirección completa: cloudinary://API_KEY:API_SECRET@CLOUD_NAME "
        '(Cloudinary > Dashboard > "API environment variable"). No alcanza con la API Key o el API Secret solos.'
    )
STORAGES = {
    "default": {"BACKEND": "backend.almacenamiento.CloudinaryStorage" if CLOUDINARY_URL
                else "django.core.files.storage.FileSystemStorage"},
    # Comprimidos (gzip/brotli) por WhiteNoise; sin manifest para que los tests no necesiten correr collectstatic
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- DRF + JWT -------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "reservas.exceptions.manejador_errores",
    # Sólo afecta a las vistas con throttle_scope (registro y login con contraseña): limita intentos por IP
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "10/min", "contacto": "5/hour"},
}

# Validadores de Django para las cuentas con contraseña (registro desde la app)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
     "OPTIONS": {"user_attributes": ("email", "nombre")}},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# --- CORS ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://localhost:3000"],
)

# --- Email (Django 6.1: MAILERS reemplaza a EMAIL_BACKEND / EMAIL_*) --------
# Al pegar la clave en Render a veces se cuelan espacios o comillas: Brevo responde "Key not found"
BREVO_API_KEY = env("BREVO_API_KEY", default="").strip().strip("'\"").strip()
if BREVO_API_KEY:
    # Producción en Render: por la API web de Brevo (HTTPS). El plan gratis de Render bloquea el SMTP saliente.
    MAILERS = {
        "default": {
            "BACKEND": "backend.email_brevo.BrevoEmailBackend",
            "OPTIONS": {"api_key": BREVO_API_KEY, "timeout": env.int("EMAIL_TIMEOUT", default=10)},
        },
    }
elif env("EMAIL_HOST", default=""):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": env("EMAIL_HOST"),
                "port": env.int("EMAIL_PORT", default=587),  # 587 con TLS (Gmail, Brevo, SendGrid...)
                "use_tls": env.bool("EMAIL_USE_TLS", default=True),
                "username": env("EMAIL_USER", default=""),
                "password": env("EMAIL_PASSWORD", default=""),
                # Sin límite, un servidor de email que no responde (o un puerto bloqueado) deja colgado el pedido
                "timeout": env.int("EMAIL_TIMEOUT", default=10),
            },
        },
    }
else:
    # En desarrollo los mails se imprimen en la consola del runserver.
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
    }
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Drivly <no-reply@drivly.local>")
# Para los logs y el diagnóstico: por dónde salen los emails (nunca incluye claves)
VIA_EMAIL = {"backend.email_brevo.BrevoEmailBackend": "API de Brevo",
             "django.core.mail.backends.smtp.EmailBackend": "SMTP"}.get(MAILERS["default"]["BACKEND"], "consola (no se envían)")
# A dónde llegan los "Sumá tu garaje" de la landing
DRIVLY_CONTACTO_EMAIL = env("CONTACTO_EMAIL", default="")

# --- Reglas de negocio (documentación, sección 1) --------------------------
DRIVLY_HOLD_TTL = timedelta(minutes=env.int("HOLD_TTL_MIN", default=5))
DRIVLY_RADIO_CERCANOS_M = env.int("RADIO_CERCANOS_M", default=1000)
# Un vehículo EN_CURSO pasado su fin (overstay activo) se proyecta ocupando hasta ahora + este margen
DRIVLY_OVERSTAY_PROYECCION = timedelta(minutes=env.int("OVERSTAY_PROYECCION_MIN", default=60))
# Overstay impago (regla 4): desde cuándo la deuda sigue a la patente, cuándo es incobrable y cuándo se recuerda
DRIVLY_DEUDA_BLOQUEO = timedelta(hours=env.int("DEUDA_BLOQUEO_HORAS", default=72))
DRIVLY_DEUDA_INCOBRABLE = timedelta(days=env.int("DEUDA_INCOBRABLE_DIAS", default=30))
DRIVLY_DEUDA_RECORDATORIOS = (timedelta(hours=0), timedelta(hours=24), timedelta(hours=48))
# Una reserva pagada se puede cancelar con reembolso total hasta este tiempo antes del inicio
DRIVLY_CANCELACION_ANTICIPACION = timedelta(minutes=env.int("CANCELACION_ANTICIPACION_MIN", default=120))
# ...o dentro de estos minutos desde el pago, para quien reserva con menos anticipación (nunca después del inicio)
DRIVLY_CANCELACION_GRACIA = timedelta(minutes=env.int("CANCELACION_GRACIA_MIN", default=10))

# --- Integraciones ---------------------------------------------------------
GOOGLE_OAUTH_CLIENT_IDS = env.list("GOOGLE_OAUTH_CLIENT_IDS", default=[])  # web + Android
MERCADOPAGO_WEBHOOK_SECRET = env("MERCADOPAGO_WEBHOOK_SECRET", default="")
# Split de pagos (Marketplace): cada garaje conecta su cuenta por OAuth y cobra en ella; Drivly retiene la comisión.
MERCADOPAGO_APP_ID = env("MP_APP_ID", default="")
MERCADOPAGO_CLIENT_SECRET = env("MP_CLIENT_SECRET", default="")
MERCADOPAGO_OAUTH_REDIRECT_URI = env("MP_OAUTH_REDIRECT_URI", default="http://localhost:8000/api/pagos/oauth/callback/")
MERCADOPAGO_TOKEN_ENCRYPTION_KEY = env("MP_TOKEN_ENCRYPTION_KEY", default="")  # clave Fernet
# True = al conectar un garaje se pide un token DE PRUEBA (test_token=true). Para demos con cuentas y tarjetas de prueba
# cuando la aplicación de Drivly está en una cuenta real de Mercado Pago. En producción real: False.
MERCADOPAGO_OAUTH_TEST_TOKEN = env.bool("MP_OAUTH_TEST_TOKEN", default=False)
DRIVLY_COMISION = Decimal(env("COMISION_DRIVLY", default="0.10"))  # 10 % de cada reserva (sección 7.2)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
# Deep link de la app Android del conductor: MP vuelve ahí al terminar el pago y la Custom Tab se cierra sola
APP_DEEPLINK_PAGO = env("APP_DEEPLINK_PAGO", default="drivly://pago-resultado")
BACKEND_URL  = env("BACKEND_URL",  default="http://localhost:8000")
DATACAR_API_URL = env("DATACAR_API_URL", default="")
DATACAR_API_KEY = env("DATACAR_API_KEY", default="")
DATACAR_MOCK = env.bool("DATACAR_MOCK", default=DEBUG)  # simulador mientras no haya credenciales

# Pagos simulados: POST /reservas/{id}/pagar/ confirma sin Mercado Pago (sólo desarrollo, Sprint 3 lo reemplaza)
DRIVLY_PAGOS_SIMULADOS = env.bool("PAGOS_SIMULADOS", default=DEBUG)

# --- Celery (expiración de holds, reintentos de patente, notificaciones) ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "expirar-holds": {
        "task": "reservas.tasks.expirar_holds",
        "schedule": 60.0,
    },
    "renovar-conexiones-mp": {
        "task": "pagos.tasks.renovar_conexiones_mp",
        "schedule": 60.0 * 60 * 24,
    },
    "reintentar-reembolsos": {
        "task": "pagos.tasks.reintentar_reembolsos",
        "schedule": 60.0 * 15,
    },
    "conciliar-pagos": {
        "task": "pagos.tasks.conciliar_pagos",
        "schedule": 60.0 * 10,
    },
    "recordar-deudas": {
        "task": "operacion.tasks.recordar_deudas",
        "schedule": 60.0 * 15,
    },
    "marcar-deudas-incobrables": {
        "task": "operacion.tasks.marcar_deudas_incobrables",
        "schedule": 60.0 * 60 * 24,
    },
    "recordar-inicios": {
        "task": "notificaciones.tasks.recordar_inicios",
        "schedule": 60.0 * 5,
    },
    "pedir-calificaciones": {
        "task": "notificaciones.tasks.pedir_calificaciones",
        "schedule": 60.0 * 10,
    },
    "avisar-fines": {
        "task": "notificaciones.tasks.avisar_fines",
        "schedule": 60.0 * 5,
    },
}

# --- Notificaciones push (Firebase Cloud Messaging, API HTTP v1) -----------
# Sin estas dos variables los push quedan desactivados; los comprobantes por email salen igual.
FCM_PROJECT_ID = env("FCM_PROJECT_ID", default="")
FCM_CREDENCIALES = env("FCM_CREDENCIALES", default="")  # ruta al JSON de la cuenta de servicio (no se sube al repo)

# --- Producción ------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# --- Logs ------------------------------------------------------------------
# Todo a la consola (es lo que muestran los Logs de Render). INFO para lo de Drivly: así se ve, por ejemplo,
# por qué vía salió cada email; WARNING para el resto de las librerías.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{levelname}] {name}: {message}", "style": "{"}},
    "handlers": {"consola": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["consola"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["consola"], "level": "INFO", "propagate": False},
        **{app: {"handlers": ["consola"], "level": "INFO", "propagate": False}
           for app in ["backend", "cuentas", "garajes", "reservas", "operacion", "pagos", "notificaciones",
                       "integraciones", "reportes", "vehiculos"]},
    },
}
