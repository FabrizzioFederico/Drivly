from django.conf import settings
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .models import Rol, Usuario

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
            usuario.save(update_fields=["google_sub"])
    if usuario is None:
        if rol_solicitado not in ROLES_AUTOREGISTRO:
            raise PermissionDenied("Los playeros deben ser dados de alta por el administrador del garaje.")
        usuario = Usuario.objects.create_user(
            email=email, nombre=info.get("name", ""), rol=rol_solicitado, google_sub=sub
        )
    if not usuario.is_active:
        raise AuthenticationFailed("La cuenta está desactivada.")
    return usuario
