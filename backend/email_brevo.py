"""
Envío de emails por la API web de Brevo (HTTPS, puerto 443).

El plan gratis de Render bloquea las conexiones SMTP salientes (también el puerto 2525): por SMTP el envío se queda
esperando hasta el timeout. Por HTTPS no hay bloqueo. Se activa con la variable BREVO_API_KEY (ver settings.MAILERS);
sin ella se sigue usando SMTP o la consola, como en desarrollo.

Funciona con cualquier email de Django: se arma el mensaje MIME completo y se traduce al formato de Brevo.
Las imágenes dentro del HTML (<img src="cid:...">, como el QR del comprobante) no se pueden mandar por la API: se suben
a Cloudinary y el HTML pasa a apuntar a esa URL. Sin Cloudinary, van como adjunto y se saca la imagen rota del HTML.
"""
import base64
import hashlib
import logging
import re
from email.utils import getaddresses, parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

URL_BREVO = "https://api.brevo.com/v3/smtp/email"


def _direcciones(lista):
    return [{"email": email, **({"name": nombre} if nombre else {})} for nombre, email in getaddresses(lista) if email]


def _url_publica(png: bytes, nombre: str) -> str | None:
    """Sube la imagen a Cloudinary con un nombre imposible de adivinar (el hash del contenido) y devuelve su URL."""
    if not settings.CLOUDINARY_URL:
        return None
    import cloudinary.uploader

    huella = hashlib.sha256(png).hexdigest()
    try:
        subida = cloudinary.uploader.upload(png, public_id=f"drivly/emails/{huella}", resource_type="image",
                                            overwrite=False)
        return subida["secure_url"]
    except Exception:
        logger.exception("No se pudo subir a Cloudinary la imagen %s del email", nombre)
        return None


def _a_brevo(mensaje) -> dict:
    """Traduce un EmailMessage de Django al JSON de POST /v3/smtp/email."""
    mime = mensaje.message()
    texto = html = None
    adjuntos, en_linea = [], []
    for parte in mime.walk():
        if parte.is_multipart():
            continue
        tipo = parte.get_content_type()
        cid = (parte.get("Content-ID") or "").strip("<>")
        disposicion = parte.get_content_disposition()
        if tipo == "text/plain" and disposicion != "attachment" and texto is None:
            texto = parte.get_content()
        elif tipo == "text/html" and disposicion != "attachment" and html is None:
            html = parte.get_content()
        elif cid and tipo.startswith("image/"):
            en_linea.append((cid, parte.get_payload(decode=True), parte.get_filename() or "imagen.png"))
        else:
            adjuntos.append({"name": parte.get_filename() or "adjunto",
                             "content": base64.b64encode(parte.get_payload(decode=True)).decode()})

    for cid, contenido, nombre in en_linea:
        url = _url_publica(contenido, nombre)
        if url and html:
            html = html.replace(f"cid:{cid}", url)
        else:
            adjuntos.append({"name": nombre, "content": base64.b64encode(contenido).decode()})
            if html:  # sin URL la imagen se vería rota: se saca y queda como adjunto
                html = re.sub(rf"<img[^>]*cid:{re.escape(cid)}[^>]*>", "", html)

    nombre, email = parseaddr(mensaje.from_email or settings.DEFAULT_FROM_EMAIL)
    datos = {
        "sender": {"email": email, **({"name": nombre} if nombre else {})},
        "to": _direcciones(mensaje.to),
        "subject": mensaje.subject,
    }
    if mensaje.cc:
        datos["cc"] = _direcciones(mensaje.cc)
    if mensaje.bcc:
        datos["bcc"] = _direcciones(mensaje.bcc)
    if mensaje.reply_to:
        datos["replyTo"] = _direcciones(mensaje.reply_to[:1])[0]  # Brevo acepta una sola dirección de respuesta
    if html:
        datos["htmlContent"] = html
    if texto:
        datos["textContent"] = texto
    if adjuntos:
        datos["attachment"] = adjuntos
    return datos


class BrevoEmailBackend(BaseEmailBackend):
    # Django 6.1 (MAILERS): cada backend maneja sus opciones, también fail_silently; a la base sólo le llega `alias`
    def __init__(self, *, api_key=None, timeout=10, fail_silently=False, alias=None, **kwargs):
        super().__init__(alias=alias, **kwargs)
        self.api_key = api_key
        self.timeout = timeout
        self.fail_silently = fail_silently

    def send_messages(self, mensajes):
        enviados = 0
        for mensaje in mensajes:
            if not mensaje.recipients():
                continue
            try:
                respuesta = requests.post(
                    URL_BREVO, json=_a_brevo(mensaje), timeout=self.timeout,
                    headers={"api-key": self.api_key, "accept": "application/json"},
                )
                if respuesta.status_code >= 400:
                    # El cuerpo explica el motivo (remitente sin verificar, IP no autorizada...); nunca trae la clave
                    raise RuntimeError(f"Brevo rechazó el email (HTTP {respuesta.status_code}): {respuesta.text[:300]}")
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("No se pudo enviar el email «%s» por Brevo", mensaje.subject)
        return enviados
