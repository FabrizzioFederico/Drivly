import pytest
from django.db import IntegrityError
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from cuentas import services
from cuentas.models import Rol, Usuario

INFO = {"sub": "google-123", "email": "Nuevo@Gmail.com", "name": "Nuevo", "email_verified": True}


def test_google_crea_conductor_por_defecto(db):
    u = services.usuario_desde_google(INFO)
    assert u.rol == Rol.CONDUCTOR and u.email == "nuevo@gmail.com" and not u.has_usable_password()


def test_google_mismo_sub_devuelve_mismo_usuario(db):
    assert services.usuario_desde_google(INFO).id == services.usuario_desde_google(INFO).id


def test_google_no_permite_autoregistro_de_playero(db):
    with pytest.raises(PermissionDenied):
        services.usuario_desde_google(INFO, Rol.PLAYERO)


def test_google_vincula_playero_creado_por_admin(garaje):
    Usuario.objects.create_user(email="nuevo@gmail.com", rol=Rol.PLAYERO, garaje=garaje)
    u = services.usuario_desde_google(INFO, Rol.CONDUCTOR)  # el rol pedido se ignora si ya existe
    assert u.rol == Rol.PLAYERO and u.google_sub == "google-123" and u.garaje == garaje


def test_google_cuenta_desactivada(db):
    services.usuario_desde_google(INFO)
    Usuario.objects.update(is_active=False)
    with pytest.raises(AuthenticationFailed):
        services.usuario_desde_google(INFO)


def test_token_de_otra_app_es_rechazado(monkeypatch, settings):
    settings.GOOGLE_OAUTH_CLIENT_IDS = ["drivly-web"]
    monkeypatch.setattr(services.id_token, "verify_oauth2_token", lambda *a, **k: {**INFO, "aud": "otra-app"})
    with pytest.raises(AuthenticationFailed):
        services.verificar_token_google("token")


def test_endpoint_google_devuelve_jwt_con_rol(db, cliente, monkeypatch):
    monkeypatch.setattr("cuentas.views.verificar_token_google", lambda t: INFO)
    r = cliente().post("/api/auth/google/", {"id_token": "x", "rol": "ADMIN_GARAJE"}, format="json")
    assert r.status_code == 200
    assert r.data["usuario"]["rol"] == "ADMIN_GARAJE" and r.data["access"] and r.data["refresh"]


def test_login_email_y_me(conductor, cliente):
    r = cliente().post("/api/auth/login/", {"email": conductor.email, "password": "clave-segura-123"})
    assert r.status_code == 200
    c = cliente()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    assert c.get("/api/auth/me/").data["email"] == conductor.email


def test_rol_no_se_puede_cambiar_desde_me(conductor, cliente):
    cliente(conductor).patch("/api/auth/me/", {"rol": "ADMIN_GARAJE", "nombre": "Lu"}, format="json")
    conductor.refresh_from_db()
    assert conductor.rol == Rol.CONDUCTOR and conductor.nombre == "Lu"


def test_db_impide_conductor_con_garaje(conductor, garaje):
    conductor.garaje = garaje
    with pytest.raises(IntegrityError):
        conductor.save()
