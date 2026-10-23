import mercadopago
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny

from reservas.exceptions import HoldVencidoSinCupo
from reservas.services import confirmar_pago


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook_mp(request):
    # Responder 200 antes de procesar — MP marca como fallido si tardamos
    # TODO: agregar validación x-signature HMAC-SHA256 → ejecutar /mp-integrate webhook
    payload = request.data

    if payload.get("type") != "payment":
        return HttpResponse(status=200)

    payment_id = payload.get("data", {}).get("id")
    if not payment_id:
        return HttpResponse(status=200)

    try:
        sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
        payment_info = sdk.payment().get(payment_id)
        payment = payment_info["response"]

        if payment.get("status") != "approved":
            return HttpResponse(status=200)

        reserva_id = payment.get("external_reference")
        if reserva_id:
            confirmar_pago(reserva_id)

    except HoldVencidoSinCupo:
        # Hold vencido sin cupo → gestionar reembolso en Sprint 4
        pass
    except Exception:
        pass  # Loguear con Sentry/structlog en producción

    return HttpResponse(status=200)
