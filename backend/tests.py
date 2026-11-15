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


# ---------- Email por la API de Brevo ----------

class _RespuestaBrevo:
    def __init__(self, status_code=201, text='{"messageId": "<1@brevo>"}'):
        self.status_code, self.text = status_code, text


def _comprobante_con_qr():
    from notificaciones.services import CID_QR, _EmailConImagenes

    m = _EmailConImagenes(subject="Reserva confirmada", body="Tu reserva está confirmada.",
                          from_email="Drivly <hola@drivly.com.ar>", to=["Ana <ana@test.com>"])
    m.attach_alternative(f'<p>Mostrá este QR</p><img src="cid:{CID_QR}" alt="QR">', "text/html")
    m.imagenes = [(CID_QR, b"\x89PNG-qr")]
    return m


def test_brevo_manda_el_comprobante_con_el_qr_subido_a_cloudinary(monkeypatch, settings):
    from backend import email_brevo

    settings.CLOUDINARY_URL = "cloudinary://1:x@demo"
    enviados = []
    monkeypatch.setattr(email_brevo.requests, "post",
                        lambda url, json, timeout, headers: enviados.append((url, json, headers)) or _RespuestaBrevo())
    import cloudinary.uploader
    monkeypatch.setattr(cloudinary.uploader, "upload",
                        lambda png, **op: {"secure_url": f"https://res.cloudinary.com/demo/{op['public_id']}.png"})

    backend = email_brevo.BrevoEmailBackend(api_key="clave-de-prueba")
    assert backend.send_messages([_comprobante_con_qr()]) == 1
    url, datos, headers = enviados[0]
    assert url == "https://api.brevo.com/v3/smtp/email" and headers["api-key"] == "clave-de-prueba"
    assert datos["sender"] == {"email": "hola@drivly.com.ar", "name": "Drivly"}
    assert datos["to"] == [{"email": "ana@test.com", "name": "Ana"}]
    assert datos["textContent"].strip() == "Tu reserva está confirmada."
    assert "cid:" not in datos["htmlContent"] and "https://res.cloudinary.com/demo/drivly/emails/" in datos["htmlContent"]
    assert "attachment" not in datos


def test_brevo_sin_cloudinary_manda_el_qr_adjunto(monkeypatch, settings):
    from backend import email_brevo

    settings.CLOUDINARY_URL = ""
    enviados = []
    monkeypatch.setattr(email_brevo.requests, "post", lambda url, json, timeout, headers: enviados.append(json) or _RespuestaBrevo())
    email_brevo.BrevoEmailBackend(api_key="k").send_messages([_comprobante_con_qr()])
    datos = enviados[0]
    assert "<img" not in datos["htmlContent"]  # sin imagen rota
    assert datos["attachment"][0]["name"] == "qr-drivly.png"


def test_brevo_contacto_con_responder_a_y_error_claro(monkeypatch):
    import pytest
    from django.core.mail import EmailMessage

    from backend import email_brevo

    enviados = []
    monkeypatch.setattr(email_brevo.requests, "post", lambda url, json, timeout, headers: enviados.append(json) or _RespuestaBrevo())
    contacto = EmailMessage(subject="Un garaje quiere sumarse", body="Hola", from_email="Drivly <hola@drivly.com.ar>",
                            to=["equipo@drivly.com.ar"], reply_to=["dueno@gmail.com"])
    email_brevo.BrevoEmailBackend(api_key="k").send_messages([contacto])
    assert enviados[0]["replyTo"] == {"email": "dueno@gmail.com"} and "htmlContent" not in enviados[0]

    monkeypatch.setattr(email_brevo.requests, "post",
                        lambda *a, **k: _RespuestaBrevo(400, '{"message": "sender not valid"}'))
    with pytest.raises(RuntimeError, match="sender not valid"):
        email_brevo.BrevoEmailBackend(api_key="k").send_messages([contacto])


def test_brevo_configurado_en_mailers_envia_con_django(monkeypatch, settings):
    """Como en Render: el backend lo crea Django desde MAILERS (send_mail, EmailMessage.send)."""
    from django.core import mail

    from backend import email_brevo

    settings.MAILERS = {"default": {"BACKEND": "backend.email_brevo.BrevoEmailBackend",
                                    "OPTIONS": {"api_key": "k", "timeout": 10}}}
    enviados = []
    monkeypatch.setattr(email_brevo.requests, "post", lambda url, json, timeout, headers: enviados.append(json) or _RespuestaBrevo())
    assert mail.send_mail("Asunto", "Cuerpo", "Drivly <hola@drivly.com.ar>", ["ana@test.com"]) == 1
    assert mail.EmailMessage("Contacto", "Hola", to=["equipo@drivly.com.ar"], reply_to=["x@y.com"]).send() == 1
    assert [d["subject"] for d in enviados] == ["Asunto", "Contacto"]

    monkeypatch.setattr(email_brevo.requests, "post", lambda *a, **k: _RespuestaBrevo(401, "Key not found"))
    assert mail.send_mail("Asunto", "Cuerpo", None, ["ana@test.com"], fail_silently=True) == 0
