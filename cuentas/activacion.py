"""
Activación de las cuentas comunes (email y contraseña) por link.

El token es el de Django para restablecer contraseñas, con otro `key_salt` y con `email_verificado` en el hash:
vence a los PASSWORD_RESET_TIMEOUT segundos (3 días), sirve una sola vez y deja de valer si la persona se
registra de nuevo (cambia la contraseña).
"""
import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import Usuario

logger = logging.getLogger(__name__)


class GeneradorActivacion(PasswordResetTokenGenerator):
    key_salt = "drivly.cuentas.activacion"

    def _make_hash_value(self, usuario, timestamp):
        return f"{usuario.pk}{usuario.password}{usuario.email}{usuario.email_verificado}{timestamp}"


generador = GeneradorActivacion()


def link(usuario) -> str:
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    return f"{settings.BACKEND_URL.rstrip('/')}/api/auth/activar/{uid}/{generador.make_token(usuario)}/"


def enviar(usuario) -> bool:
    """Manda el email con el link. Devuelve False si el SMTP falló (la persona puede pedir que se reenvíe)."""
    contexto = {"nombre": usuario.nombre, "link": link(usuario), "dias": settings.PASSWORD_RESET_TIMEOUT // 86400}
    mensaje = EmailMultiAlternatives(
        subject="Drivly: activá tu cuenta",
        body=render_to_string("cuentas/activacion.txt", contexto),
        from_email=None,
        to=[usuario.email],
    )
    mensaje.attach_alternative(render_to_string("cuentas/activacion.html", contexto), "text/html")
    try:
        mensaje.send()
    except Exception:
        logger.exception("No se pudo mandar el email de activación a %s", usuario.pk)
        return False
    return True


def activar(uidb64: str, token: str):
    """Activa la cuenta si el link es válido. Devuelve el usuario, o None si el link venció o ya se usó."""
    try:
        usuario = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    if usuario.email_verificado:
        return usuario  # ya estaba activa: tocar el link otra vez no es un error
    if not generador.check_token(usuario, token):
        return None
    usuario.email_verificado = True
    usuario.save(update_fields=["email_verificado"])
    return usuario
