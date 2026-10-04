from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from cuentas.models import Rol, Usuario
from garajes.models import Garaje

CUIT_VALIDO = "30-71234567-1"


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
