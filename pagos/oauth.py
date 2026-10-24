"""
Conexión de la cuenta de Mercado Pago de cada garaje (OAuth de Marketplace).

1. El admin pide la URL de autorización: se crea un `state` aleatorio de un solo uso ligado a él y al garaje.
2. Mercado Pago vuelve al callback con `code` y `state`: se consume el state y se canjea el code en /oauth/token.
3. Los tokens se guardan cifrados. Antes de vencer se renuevan con el refresh_token (que MP puede rotar).
"""
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .exceptions import GarajeSinMercadoPago, OAuthError
from .models import ConexionMP, EstadoOAuth

logger = logging.getLogger(__name__)

URL_AUTORIZACION = "https://auth.mercadopago.com/authorization"
URL_TOKEN = "https://api.mercadopago.com/oauth/token"
STATE_TTL = timedelta(minutes=10)
MARGEN_RENOVACION = timedelta(days=7)  # se renueva cuando faltan menos de 7 días para que venza


def url_autorizacion(usuario, garaje) -> str:
    state = secrets.token_urlsafe(32)
    EstadoOAuth.objects.create(state=state, usuario=usuario, garaje=garaje, expira_en=timezone.now() + STATE_TTL)
    params = {
        "client_id": settings.MERCADOPAGO_APP_ID,
        "response_type": "code",
        "platform_id": "mp",
        "redirect_uri": settings.MERCADOPAGO_OAUTH_REDIRECT_URI,
        "state": state,
    }
    return f"{URL_AUTORIZACION}?{urlencode(params)}"


@transaction.atomic
def consumir_state(state) -> EstadoOAuth:
    """Marca el state como usado. Uno inexistente, vencido o ya usado se rechaza."""
    estado = EstadoOAuth.objects.select_for_update().select_related("garaje").filter(
        state=state or "", usado_en__isnull=True, expira_en__gt=timezone.now()
    ).first()
    if estado is None:
        raise OAuthError("El state de OAuth no existe, venció o ya se usó.")
    estado.usado_en = timezone.now()
    estado.save(update_fields=["usado_en"])
    return estado


def _pedir_token(datos) -> dict:
    """POST form-urlencoded a /oauth/token (requests codifica `data=` como application/x-www-form-urlencoded)."""
    try:
        r = requests.post(URL_TOKEN, timeout=10, headers={"Accept": "application/json"}, data={
            "client_id": settings.MERCADOPAGO_APP_ID, "client_secret": settings.MERCADOPAGO_CLIENT_SECRET, **datos,
        })
    except requests.RequestException as e:
        raise OAuthError(f"Mercado Pago no respondió: {e.__class__.__name__}") from e
    if r.status_code >= 400:
        raise OAuthError(f"Mercado Pago rechazó el canje de tokens ({r.status_code}).")
    return r.json()


def _guardar(conexion, respuesta):
    conexion.guardar_tokens(
        access_token=respuesta["access_token"], refresh_token=respuesta["refresh_token"],
        expira_en=timezone.now() + timedelta(seconds=int(respuesta["expires_in"])), scope=respuesta.get("scope"),
    )


def conectar(state, code) -> ConexionMP:
    """Callback de OAuth: consume el state, canjea el code y guarda la conexión del garaje."""
    estado = consumir_state(state)
    if not code:
        raise OAuthError("Mercado Pago no devolvió el código de autorización.")
    if estado.garaje.admin_id != estado.usuario_id:
        raise OAuthError("El usuario que inició la conexión ya no administra ese garaje.")
    respuesta = _pedir_token({
        "grant_type": "authorization_code", "code": code, "redirect_uri": settings.MERCADOPAGO_OAUTH_REDIRECT_URI,
    })
    with transaction.atomic():
        conexion = (ConexionMP.objects.select_for_update().filter(garaje=estado.garaje).first()
                    or ConexionMP(garaje=estado.garaje))
        conexion.mp_user_id = str(respuesta["user_id"])
        _guardar(conexion, respuesta)
        conexion.save()
    return conexion


def access_token_de(garaje) -> str:
    """Token vigente del garaje para cobrar en su cuenta. Nunca cae al token de Drivly."""
    conexion = ConexionMP.objects.filter(garaje=garaje).first()
    if conexion is None or conexion.requiere_reautorizar:
        raise GarajeSinMercadoPago()
    if conexion.expira_en - timezone.now() > MARGEN_RENOVACION:
        return conexion.access_token
    token = _renovar(conexion.pk)
    if token is None:
        raise GarajeSinMercadoPago()
    return token


def _renovar(conexion_id):
    """Renueva ambos tokens bajo bloqueo. Si MP lo rechaza, marca la conexión para reautorizar y devuelve None."""
    with transaction.atomic():
        conexion = ConexionMP.objects.select_for_update().get(pk=conexion_id)
        if conexion.expira_en - timezone.now() > MARGEN_RENOVACION:  # otro proceso ya la renovó
            return conexion.access_token
        try:
            respuesta = _pedir_token({"grant_type": "refresh_token", "refresh_token": conexion.refresh_token})
        except OAuthError as e:
            logger.error("No se pudo renovar la conexión de MP del garaje %s: %s", conexion.garaje_id, e)
            conexion.requiere_reautorizar = True
            conexion.save(update_fields=["requiere_reautorizar", "actualizada_en"])
            return None
        _guardar(conexion, respuesta)
        conexion.save()
        return conexion.access_token


def renovar_por_vencer() -> int:
    """Tarea diaria: renueva las conexiones que vencen pronto aunque el garaje no haya tenido reservas."""
    limite = timezone.now() + MARGEN_RENOVACION
    ids = ConexionMP.objects.filter(requiere_reautorizar=False, expira_en__lte=limite).values_list("pk", flat=True)
    return sum(1 for pk in ids if _renovar(pk) is not None)
