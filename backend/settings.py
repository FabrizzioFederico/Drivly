"""
Configuración de Drivly (Django 6.1).
Todos los valores sensibles o que cambian por entorno se leen de variables de entorno (.env).
"""
from datetime import timedelta
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
]

# Usuario propio: definirlo ANTES de la primera migración del proyecto.
AUTH_USER_MODEL = "cuentas.Usuario"

# CorsMiddleware va primero (siempre antes de CommonMiddleware) y sin duplicados.
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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
STATIC_ROOT = BASE_DIR / "staticfiles"

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
}

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
if env("EMAIL_HOST", default=""):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": env("EMAIL_HOST"),
                "use_tls": env.bool("EMAIL_USE_TLS", default=True),
                "username": env("EMAIL_USER", default=""),
                "password": env("EMAIL_PASSWORD", default=""),
            },
        },
    }
else:
    # En desarrollo los mails se imprimen en la consola del runserver.
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
    }
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Drivly <no-reply@drivly.local>")

# --- Reglas de negocio (documentación, sección 1) --------------------------
DRIVLY_HOLD_TTL = timedelta(minutes=env.int("HOLD_TTL_MIN", default=5))
DRIVLY_RADIO_CERCANOS_M = env.int("RADIO_CERCANOS_M", default=1000)

# --- Integraciones ---------------------------------------------------------
GOOGLE_OAUTH_CLIENT_IDS = env.list("GOOGLE_OAUTH_CLIENT_IDS", default=[])  # web + Android
MERCADOPAGO_ACCESS_TOKEN = env("MERCADOPAGO_ACCESS_TOKEN", default="")
MERCADOPAGO_WEBHOOK_SECRET = env("MERCADOPAGO_WEBHOOK_SECRET", default="")
PATENTE_AR_API_KEY = env("PATENTE_AR_API_KEY", default="")
PATENTE_AR_MOCK = env.bool("PATENTE_AR_MOCK", default=DEBUG)  # mock mientras no haya contrato

# --- Celery (expiración de holds, reintentos de patente, notificaciones) ---
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "expirar-holds": {
        "task": "reservas.tasks.expirar_holds",
        "schedule": 60.0,
    },
}

# --- Producción ------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True