"""Configuración de producción: fotos en Cloudinary y archivos estáticos del admin con DEBUG=False."""
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import Client

from backend import almacenamiento
from backend.almacenamiento import CloudinaryStorage


def test_cloudinary_sube_arma_la_url_y_borra(monkeypatch):
    llamadas = []
    monkeypatch.setattr(almacenamiento.cloudinary.uploader, "upload",
                        lambda archivo, **op: llamadas.append(("subir", archivo.read(), op)))
    monkeypatch.setattr(almacenamiento.cloudinary.uploader, "destroy",
                        lambda public_id, **op: llamadas.append(("borrar", public_id)))
    monkeypatch.setattr(almacenamiento.cloudinary.utils, "cloudinary_url",
                        lambda public_id, **op: (f"https://res.cloudinary.com/demo/image/upload/{public_id}.{op['format']}", {}))

    storage = CloudinaryStorage()
    nombre = storage.save("garajes/abc/123.jpg", ContentFile(b"jpeg", name="foto.jpg"))
    assert nombre == "garajes/abc/123.jpg"
    _, contenido, opciones = llamadas[0]
    assert contenido == b"jpeg" and opciones["public_id"] == "drivly/garajes/abc/123"
    assert storage.url(nombre) == "https://res.cloudinary.com/demo/image/upload/drivly/garajes/abc/123.jpg"
    storage.delete(nombre)
    assert llamadas[-1] == ("borrar", "drivly/garajes/abc/123")


def test_admin_con_estilos_y_fotos_locales_con_debug_false(settings, tmp_path, db):
    settings.DEBUG = False
    settings.SECURE_SSL_REDIRECT = False
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("collectstatic", "--noinput", verbosity=0)
    (tmp_path / "media" / "fotos").mkdir(parents=True)
    (tmp_path / "media" / "fotos" / "x.jpg").write_bytes(b"jpeg")

    c = Client()  # cliente nuevo: WhiteNoise lee STATIC_ROOT al arrancar
    assert c.get("/static/admin/css/base.css").status_code == 200
    assert c.get("/api/media/fotos/x.jpg").status_code == 200


def test_si_cloudinary_rechaza_la_subida_responde_503_claro(monkeypatch):
    import pytest

    def rechazar(*a, **k):
        raise Exception("Error 401 - cloud_name mismatch")

    monkeypatch.setattr(almacenamiento.cloudinary.uploader, "upload", rechazar)
    monkeypatch.setattr(almacenamiento.cloudinary.uploader, "destroy", rechazar)
    with pytest.raises(almacenamiento.FotoNoDisponible) as error:
        CloudinaryStorage().save("fotos/x.jpg", ContentFile(b"jpeg", name="x.jpg"))
    assert error.value.status_code == 503
    CloudinaryStorage().delete("fotos/vieja.jpg")  # borrar una vieja que falla no rompe nada
