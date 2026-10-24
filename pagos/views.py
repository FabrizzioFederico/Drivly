import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from cuentas.permissions import EsAdminGaraje
from garajes.models import Garaje

from . import oauth
from .exceptions import OAuthError
from .models import ConexionMP, ResultadoPago
from .services import firma_valida, procesar_notificacion_pago

logger = logging.getLogger(__name__)


def _garaje_propio(request, garaje_id):
    return get_object_or_404(Garaje, pk=garaje_id, admin=request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated, EsAdminGaraje])
def oauth_conectar(request):
    """POST /api/pagos/oauth/conectar/ {garaje} -> {url}: el frontend redirige al admin a Mercado Pago."""
    garaje = _garaje_propio(request, request.data.get("garaje"))
    return Response({"url": oauth.url_autorizacion(request.user, garaje)})


@api_view(["GET"])
@permission_classes([IsAuthenticated, EsAdminGaraje])
def oauth_estado(request):
    """GET /api/pagos/oauth/estado/?garaje= -> {conectado, requiere_reautorizar}. Nunca devuelve tokens."""
    conexion = ConexionMP.objects.filter(garaje=_garaje_propio(request, request.query_params.get("garaje"))).first()
    return Response({
        "conectado": conexion is not None and not conexion.requiere_reautorizar,
        "requiere_reautorizar": bool(conexion and conexion.requiere_reautorizar),
        "conectada_en": conexion.conectada_en if conexion else None,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def oauth_callback(request):
    """
    GET /api/pagos/oauth/callback/?code=&state=  (redirect URI configurada en el panel de MP)
    El usuario llega sin JWT: el state de un solo uso identifica al admin y al garaje.
    """
    params = request.query_params
    resultado = "ok"
    try:
        if params.get("error"):  # el admin rechazó la autorización
            oauth.consumir_state(params.get("state"))
            raise OAuthError(f"Mercado Pago devolvió error={params['error']}")
        oauth.conectar(params.get("state"), params.get("code"))
    except OAuthError as e:
        logger.warning("Conexión de Mercado Pago fallida: %s", e)
        resultado = "error"
    except Exception:
        # Error nuestro (base, cifrado...): queda en el log y el admin vuelve a la app con un mensaje, no a un 500.
        logger.exception("Error inesperado guardando la conexión de Mercado Pago")
        resultado = "error"
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/?mp_conexion={resultado}")


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook_mp(request):
    """
    POST /api/pagos/webhook/?data.id=<payment_id>&type=payment
    Responde 200 cuando el pago quedó procesado y 500 cuando hay que reintentar (MP reenvía la notificación).
    """
    data = request.data.get("data") or {}
    data_id = request.query_params.get("data.id") or str(data.get("id") or "")
    tipo = request.query_params.get("type") or request.data.get("type")

    if not firma_valida(request.headers.get("x-signature", ""), request.headers.get("x-request-id", ""), data_id):
        logger.warning("Webhook de MP con firma inválida (data.id=%r)", data_id)
        return HttpResponse(status=401)

    if tipo != "payment" or not data_id:
        return HttpResponse(status=200)

    try:
        # user_id: la cuenta del garaje que cobró. Hace falta su token para consultar el pago.
        pago = procesar_notificacion_pago(data_id, request.data.get("user_id"))
    except Exception:
        logger.exception("Error procesando el pago %s de Mercado Pago", data_id)
        return HttpResponse(status=500)

    if pago is not None and pago.resultado == ResultadoPago.REEMBOLSO_FALLIDO:
        return HttpResponse(status=500)
    return HttpResponse(status=200)
