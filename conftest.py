from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from cuentas.models import Rol, Usuario
from garajes.models import Garaje

CUIT_VALIDO = "30-71234567-1"
CLAVE_CIFRADO_TESTS = Fernet.generate_key().decode()


class _SDKBloqueado:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Un test intentó conectarse a Mercado Pago: usá el fixture `mp` de pagos/tests.py.")


@pytest.fixture(autouse=True)
def _aislar_de_mercado_pago(settings, monkeypatch):
    """Los tests no dependen del .env ni llaman a Mercado Pago de verdad."""
    settings.MERCADOPAGO_WEBHOOK_SECRET = "secreto-de-tests"
    settings.MERCADOPAGO_APP_ID = "app-de-tests"
    settings.MERCADOPAGO_CLIENT_SECRET = "client-secret-de-tests"
    settings.MERCADOPAGO_OAUTH_REDIRECT_URI = "http://localhost:8000/api/pagos/oauth/callback/"
    settings.MERCADOPAGO_TOKEN_ENCRYPTION_KEY = CLAVE_CIFRADO_TESTS
    settings.DRIVLY_COMISION = Decimal("0.10")
    settings.DRIVLY_PAGOS_SIMULADOS = False
    settings.FRONTEND_URL = "http://localhost:5173"
    settings.BACKEND_URL = "http://localhost:8000"
    monkeypatch.setattr("mercadopago.SDK", _SDKBloqueado)
    monkeypatch.setattr("pagos.oauth.requests.post", _SDKBloqueado)


@pytest.fixture
def crear_usuario(db):
    def _crear(email, rol=Rol.CONDUCTOR, **extra):
        return Usuario.objects.create_user(email=email, password="clave-segura-123", rol=rol, **extra)
    return _crear


@pytest.fixture
def conductor(crear_usuario):
    return crear_usuario("lucia@test.com")


@pytest.fixture
def admin_garaje(crear_usuario):
    return crear_usuario("raul@test.com", rol=Rol.ADMIN_GARAJE)


@pytest.fixture
def otro_admin(crear_usuario):
    return crear_usuario("otro@test.com", rol=Rol.ADMIN_GARAJE)


@pytest.fixture
def garaje(admin_garaje):
    # Palermo, Buenos Aires
    return Garaje.objects.create(
        admin=admin_garaje, nombre="Garaje Palermo", cuit=CUIT_VALIDO, direccion="Gorriti 4800",
        lat=Decimal("-34.588000"), lng=Decimal("-58.430000"), capacidad=50, cupo_abonos=10,
    )


@pytest.fixture
def cliente():
    def _cliente(usuario=None):
        c = APIClient()
        if usuario:
            c.force_authenticate(usuario)
        return c
    return _cliente
