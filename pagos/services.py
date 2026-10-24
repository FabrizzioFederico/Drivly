import hashlib
import hmac
import logging
from decimal import ROUND_HALF_UP, Decimal

import mercadopago
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from reservas.exceptions import EstadoInvalido, HoldVencidoSinCupo
from reservas.models import Reserva
from reservas.services import confirmar_pago

from .models import ConexionMP, Pago, ResultadoPago
from .oauth import access_token_de

logger = logging.getLogger(__name__)

# Resultados que todavía hay que (re)procesar cuando MP vuelve a notificar el mismo pago
RESULTADOS_A_PROCESAR = (ResultadoPago.PENDIENTE, ResultadoPago.REEMBOLSO_FALLIDO)


def _sdk(access_token):
    """Único punto de creación del SDK: los tests lo reemplazan por un doble."""
    return mercadopago.SDK(access_token)


def _fecha_mp(dt) -> str:
    """Formato que pide MP: 2026-10-24T14:05:00.000-03:00"""
    return timezone.localtime(dt).isoformat(timespec="milliseconds")


def calcular_comision(monto: Decimal) -> Decimal:
    """Comisión de Drivly sobre el monto congelado de la reserva. Nunca viene del navegador."""
    comision = (monto * settings.DRIVLY_COMISION).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not (Decimal("0") <= comision < monto):
        raise ValueError(f"Comisión inválida ({comision}) para un monto de {monto}.")
    return comision


def crear_preferencia(reserva) -> str:
    """
    Crea una preferencia de Checkout Pro en la cuenta del garaje (POST /checkout/preferences con su token OAuth)
    y devuelve init_point. MP acredita el pago al garaje y le transfiere a Drivly el marketplace_fee.
    """
    sdk = _sdk(access_token_de(reserva.garaje))  # GarajeSinMercadoPago (409) si el garaje no conectó su cuenta

    frontend_url = settings.FRONTEND_URL
    backend_url  = settings.BACKEND_URL

    # auto_return solo funciona con URL pública HTTPS
    # MP rechaza la preferencia si back_urls.success es localhost
    es_url_publica = (
        frontend_url.startswith("https://")
        and "localhost" not in frontend_url
        and "127.0.0.1" not in frontend_url
    )

    preference_data = {
        "items": [{
            "title": f"Reserva Drivly · {reserva.garaje.nombre}",
            "quantity": 1,
            "unit_price": float(reserva.monto),
            "currency_id": "ARS",
        }],
        "back_urls": {
            "success": f"{frontend_url}/?mp_status=success",
            "failure": f"{frontend_url}/?mp_status=failure",
            "pending": f"{frontend_url}/?mp_status=pending",
        },
        "external_reference": str(reserva.id),
        "marketplace_fee": float(calcular_comision(reserva.monto)),
        "notification_url": f"{backend_url}/api/pagos/webhook/",
        "statement_descriptor": "DRIVLY",
        # La preferencia vence junto con el hold: pasado ese momento MP no deja pagar.
        "expires": True,
        "expiration_date_from": _fecha_mp(timezone.now()),
        "expiration_date_to": _fecha_mp(reserva.hold_expira),
        # Efectivo (Rapipago, Pago Fácil) se acredita en horas o días: no sirve para un hold de 5 minutos.
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
        **({"auto_return": "approved"} if es_url_publica else {}),
    }

    result = sdk.preference().create(preference_data)
    if result["status"] >= 400:
        raise RuntimeError(f"Error creando preferencia MP: {result['response']}")

    # MP ya no tiene sandbox: las pruebas usan usuarios de prueba con el mismo init_point.
    return result["response"]["init_point"]


# ---------- Webhook ----------

def firma_valida(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """
    Valida el header x-signature (HMAC-SHA256 con la clave secreta del panel de Webhooks).
    Sin clave configurada se rechaza todo: no se aceptan notificaciones sin verificar.
    """
    secreto = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not secreto or not x_signature:
        return False
    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    # MP arma el manifest sólo con los valores presentes; el id va en minúsculas.
    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    esperado = hmac.new(secreto.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def procesar_notificacion_pago(payment_id, mp_user_id):
    """
    Consulta el pago en MP con el token del garaje que lo cobró (`mp_user_id` de la notificación),
    lo registra y actúa. Idempotente: MP puede notificar el mismo pago varias veces.
      - approved y monto correcto -> confirma la reserva.
      - approved pero la reserva ya no se puede confirmar (hold vencido sin cupo, cancelada) -> reembolso.
      - approved con monto distinto -> no confirma, queda MONTO_INCORRECTO para revisión.
    Devuelve el Pago, o None si el pago no corresponde a una reserva de Drivly.
    Los errores de red o de MP se propagan: el webhook responde 500 y MP reintenta.
    """
    conexion = ConexionMP.objects.select_related("garaje").filter(mp_user_id=str(mp_user_id or "")).first()
    if conexion is None:
        raise RuntimeError(f"Notificación del pago {payment_id} de una cuenta de MP sin garaje conectado "
                           f"(user_id={mp_user_id!r})")
    sdk = _sdk(access_token_de(conexion.garaje))
    respuesta = sdk.payment().get(payment_id)
    if respuesta["status"] >= 400:
        raise RuntimeError(f"Error consultando el pago {payment_id} en MP: {respuesta['response']}")
    payment = respuesta["response"]

    try:
        reserva = Reserva.objects.filter(pk=payment.get("external_reference")).first()
    except ValidationError:  # external_reference que no es un UUID
        reserva = None
    if reserva is None:
        logger.warning("Pago %s de MP sin reserva asociada (external_reference=%r)",
                       payment_id, payment.get("external_reference"))
        return None
    # Un pago acreditado en la cuenta de otro garaje no confirma esta reserva.
    if not ConexionMP.objects.filter(garaje_id=reserva.garaje_id, mp_user_id=conexion.mp_user_id).exists():
        logger.error("Pago %s cobrado por la cuenta MP %s, que no es la del garaje de la reserva %s",
                     payment_id, conexion.mp_user_id, reserva.id)
        return None

    with transaction.atomic():
        # El bloqueo serializa notificaciones simultáneas del mismo pago: evita reembolsar dos veces.
        pago, _ = Pago.objects.select_for_update().get_or_create(
            payment_id=str(payment["id"]),
            defaults={"reserva": reserva, "monto": Decimal(str(payment.get("transaction_amount") or 0)),
                      "comision": calcular_comision(reserva.monto)},
        )
        pago.estado_mp = payment.get("status", "")
        pago.estado_detalle_mp = payment.get("status_detail") or ""
        pago.datos_mp = payment
        pago.save()

        if pago.estado_mp != "approved" or pago.resultado not in RESULTADOS_A_PROCESAR:
            return pago

        if pago.monto != reserva.monto or payment.get("currency_id") != "ARS":
            logger.error("Pago %s: pagó %s %s y la reserva %s cuesta %s ARS. No se confirma.",
                         pago.payment_id, pago.monto, payment.get("currency_id"), reserva.id, reserva.monto)
            pago.resultado = ResultadoPago.MONTO_INCORRECTO
            pago.save(update_fields=["resultado", "actualizado_en"])
            return pago

        try:
            confirmar_pago(reserva.id)
        except (HoldVencidoSinCupo, EstadoInvalido) as e:
            logger.warning("Pago %s aprobado pero la reserva %s no se puede confirmar (%s): se reembolsa.",
                           pago.payment_id, reserva.id, e.default_code)
            _reembolsar(pago, sdk)
        else:
            pago.resultado = ResultadoPago.CONFIRMO_RESERVA
            pago.save(update_fields=["resultado", "actualizado_en"])
    return pago


def _reembolsar(pago, sdk):
    """
    Reembolso total desde la cuenta del garaje (el pago es suyo). Si falla queda REEMBOLSO_FALLIDO
    y el webhook responde 500 para que MP reintente.
    """
    try:
        respuesta = sdk.refund().create(pago.payment_id)
        if respuesta["status"] >= 400:
            raise RuntimeError(respuesta["response"])
    except Exception:
        logger.exception("No se pudo reembolsar el pago %s de la reserva %s", pago.payment_id, pago.reserva_id)
        pago.resultado = ResultadoPago.REEMBOLSO_FALLIDO
    else:
        pago.resultado = ResultadoPago.REEMBOLSADO
        pago.reembolso_id = str(respuesta["response"].get("id", ""))
    pago.save(update_fields=["resultado", "reembolso_id", "actualizado_en"])
