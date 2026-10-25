import pathlib
import re
from datetime import timedelta
from io import BytesIO

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from PIL import Image
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from cuentas import services
from cuentas.models import CambioEmail, Rol, Usuario

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
    assert r.data["user"]["rol"] == "ADMIN_GARAJE" and r.data["access"] and r.data["refresh"]


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


# ---------- Perfil editable ----------

@pytest.fixture(autouse=True)
def _media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path  # las fotos de los tests no ensucian media/


def _imagen(ancho=2000, alto=1000, formato="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (ancho, alto), (0, 102, 255)).save(buffer, format=formato)
    return SimpleUploadedFile(f"foto.{formato.lower()}", buffer.getvalue(), content_type=f"image/{formato.lower()}")


def test_editar_nombre_genero_y_telefono(conductor, cliente):
    r = cliente(conductor).patch("/api/auth/me/", {"nombre": "Lucía", "genero": "FEMENINO", "telefono": "+54 9 11 1234-5678"},
                                 format="json")
    assert r.status_code == 200 and (r.data["nombre"], r.data["genero"], r.data["telefono"]) == ("Lucía", "FEMENINO", "+54 9 11 1234-5678")


@pytest.mark.parametrize("campo, valor", [("telefono", "abc"), ("telefono", "123"), ("genero", "OTRO")])
def test_datos_de_perfil_invalidos(conductor, cliente, campo, valor):
    assert cliente(conductor).patch("/api/auth/me/", {campo: valor}, format="json").status_code == 400


def test_el_email_no_se_cambia_por_patch(conductor, cliente):
    cliente(conductor).patch("/api/auth/me/", {"email": "otro@test.com"}, format="json")
    conductor.refresh_from_db()
    assert conductor.email == "lucia@test.com"


def test_foto_se_recorta_y_achica(conductor, cliente):
    r = cliente(conductor).put("/api/auth/me/foto/", {"foto": _imagen()}, format="multipart")
    assert r.status_code == 200 and r.data["foto"].startswith("/api/media/fotos/")
    conductor.refresh_from_db()
    with Image.open(conductor.foto.path) as guardada:
        assert guardada.size == (512, 512) and guardada.format == "JPEG"


def test_nueva_foto_borra_la_anterior_y_delete_la_quita(conductor, cliente):
    c = cliente(conductor)
    c.put("/api/auth/me/foto/", {"foto": _imagen()}, format="multipart")
    conductor.refresh_from_db()
    primera = pathlib.Path(conductor.foto.path)
    c.put("/api/auth/me/foto/", {"foto": _imagen(formato="JPEG")}, format="multipart")
    assert not primera.exists()
    assert c.delete("/api/auth/me/foto/").data["foto"] is None


def test_foto_que_no_es_imagen(conductor, cliente):
    falso = SimpleUploadedFile("foto.png", b"esto no es una imagen", content_type="image/png")
    r = cliente(conductor).put("/api/auth/me/foto/", {"foto": falso}, format="multipart")
    assert r.status_code == 400 and "foto" in r.data


def _codigo_del_mail():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def test_cambio_de_email_con_codigo(conductor, cliente):
    c = cliente(conductor)
    r = c.post("/api/auth/me/email/", {"email": "Nueva@Test.com"}, format="json")
    assert r.status_code == 202 and mail.outbox[-1].to == ["nueva@test.com"]
    conductor.refresh_from_db()
    assert conductor.email == "lucia@test.com"  # todavía no cambió
    assert c.post("/api/auth/me/email/confirmar/", {"codigo": _codigo_del_mail()}, format="json").data["email"] == "nueva@test.com"
    assert not CambioEmail.objects.exists()


def test_codigo_incorrecto_y_limite_de_intentos(conductor, cliente):
    c = cliente(conductor)
    c.post("/api/auth/me/email/", {"email": "nueva@test.com"}, format="json")
    correcto = _codigo_del_mail()
    incorrecto = "000000" if correcto != "000000" else "111111"
    for _ in range(5):
        assert c.post("/api/auth/me/email/confirmar/", {"codigo": incorrecto}, format="json").status_code == 400
    # Agotados los intentos ni el código correcto sirve: hay que pedir otro
    assert c.post("/api/auth/me/email/confirmar/", {"codigo": correcto}, format="json").status_code == 400
    conductor.refresh_from_db()
    assert conductor.email == "lucia@test.com"


def test_codigo_vencido(conductor, cliente):
    c = cliente(conductor)
    c.post("/api/auth/me/email/", {"email": "nueva@test.com"}, format="json")
    CambioEmail.objects.update(expira=timezone.now() - timedelta(seconds=1))
    assert c.post("/api/auth/me/email/confirmar/", {"codigo": _codigo_del_mail()}, format="json").status_code == 400


def test_email_de_otra_cuenta(conductor, admin_garaje, cliente):
    r = cliente(conductor).post("/api/auth/me/email/", {"email": admin_garaje.email}, format="json")
    assert r.status_code == 400 and not mail.outbox
