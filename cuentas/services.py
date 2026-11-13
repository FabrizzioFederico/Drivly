import logging
import re
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .models import Rol, Usuario
from .perfil import guardar_foto

log = logging.getLogger(__name__)

ROLES_AUTOREGISTRO = {Rol.CONDUCTOR, Rol.ADMIN_GARAJE}  # el playero lo da de alta su admin


def verificar_token_google(token: str) -> dict:
    """Valida firma, vencimiento y audiencia del ID token que manda la app o la web."""
    try:
        info = id_token.verify_oauth2_token(token, google_requests.Request())
    except ValueError as error:
        raise AuthenticationFailed(f"Token de Google inválido: {error}")
    if info.get("aud") not in settings.GOOGLE_OAUTH_CLIENT_IDS:
        raise AuthenticationFailed("El token no fue emitido para Drivly.")
    if not info.get("email_verified"):
        raise AuthenticationFailed("El email de Google no está verificado.")
    return info


@transaction.atomic
def usuario_desde_google(info: dict, rol_solicitado: str = Rol.CONDUCTOR) -> Usuario:
    """
    1. Ya entró antes con Google -> mismo usuario.
    2. Existe con ese email (ej. playero creado por su admin) -> se vincula la cuenta de Google.
    3. No existe -> se crea con el rol pedido (sólo conductor o admin de garaje).
    """
    sub, email = info["sub"], info["email"].lower()

    usuario = Usuario.objects.filter(google_sub=sub).first()
    if usuario is None:
        usuario = Usuario.objects.select_for_update().filter(email=email).first()
        if usuario is not None:
            usuario.google_sub = sub
            # Google verificó el email: si la cuenta común estaba pendiente de activación, queda activada
            usuario.email_verificado = True
            campos = ["google_sub", "email_verificado"]
            if usuario.has_usable_password():
                # El registro con contraseña no verifica el email: si alguien creó la cuenta con un email ajeno,
                # el dueño real (que Google sí verificó) no debe compartirla con esa contraseña.
                usuario.set_unusable_password()
                campos.append("password")
            usuario.save(update_fields=campos)
    if usuario is None:
        if rol_solicitado not in ROLES_AUTOREGISTRO:
            raise PermissionDenied("Los playeros deben ser dados de alta por el administrador del garaje.")
        usuario = Usuario.objects.create_user(
            email=email, nombre=info.get("name", ""), rol=rol_solicitado, google_sub=sub
        )
    if not usuario.is_active:
        raise AuthenticationFailed("La cuenta está desactivada.")
    return usuario


def copiar_foto_de_google(usuario: Usuario, info: dict) -> None:
    """
    Si la cuenta no tiene foto, usa la de la cuenta de Google (el claim `picture` del ID token).
    Nunca pisa una foto que la persona eligió, y si Google no responde la cuenta queda sin foto: el login sigue igual.
    """
    url = info.get("picture") or ""
    if usuario.foto or not url:
        return
    if not (urlparse(url).hostname or "").endswith(".googleusercontent.com"):
        return  # sólo se descargan imágenes de Google
    url = re.sub(r"=s\d+(-c)?$", "=s512-c", url)  # Google la manda de 96 px: se pide de 512
    try:
        respuesta = requests.get(url, timeout=5)
        respuesta.raise_for_status()
        guardar_foto(usuario, ContentFile(respuesta.content, name="google.jpg"))
    except Exception as error:  # red caída, imagen rota, archivo enorme
        log.warning("No se pudo copiar la foto de Google de %s: %s", usuario.email, error)
