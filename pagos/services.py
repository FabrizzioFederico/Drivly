import hashlib
import hmac
import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import mercadopago
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from operacion.models import Deuda, EstadoDeuda, MedioCobro
from operacion.services import saldar_deuda
from reservas.exceptions import EstadoInvalido, HoldVencidoSinCupo, PagosNoDisponibles
from reservas.models import EstadoReserva, Reserva
from reservas.services import confirmar_pago

from .exceptions import GarajeSinMercadoPago
from .models import ConexionMP, Pago, ResultadoPago
from .oauth import access_token_de

logger = logging.getLogger(__name__)

# Resultados que todavía hay que (re)procesar cuando MP vuelve a notificar el mismo pago
RESULTADOS_A_PROCESAR = (ResultadoPago.PENDIENTE, ResultadoPago.REEMBOLSO_FALLIDO)

# Desde dónde paga el conductor: define a dónde vuelve Mercado Pago al terminar
CANAL_WEB, CANAL_APP = "web", "app"
CANALES = (CANAL_WEB, CANAL_APP)

# external_reference de los cobros de overstay; el de las reservas es sólo el id
PREFIJO_DEUDA = "deuda:"


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


def _retorno(canal):
    """Cómo vuelve el conductor del checkout: back_urls y, si se puede, auto_return."""
    frontend_url = settings.FRONTEND_URL

    if canal == CANAL_APP:
        # App Android: MP vuelve al deep link y la Custom Tab se cierra sola (doc. Checkout Pro mobile)
        base, auto_return = f"{settings.APP_DEEPLINK_PAGO}?", True
    else:
        # auto_return solo funciona con URL pública HTTPS
        # MP rechaza la preferencia si back_urls.success es localhost
        auto_return = (
            frontend_url.startswith("https://")
            and "localhost" not in frontend_url
            and "127.0.0.1" not in frontend_url
        )
        base = f"{frontend_url}/?"

    return {
        "back_urls": {
            "success": f"{base}mp_status=success",
            "failure": f"{base}mp_status=failure",
            "pending": f"{base}mp_status=pending",
        },
        **({"auto_return": "approved"} if auto_return else {}),
    }


def _abrir_checkout(garaje, datos, que, detalle_error=None) -> str:
    """
    Crea la preferencia en la cuenta del garaje y devuelve init_point. Si Mercado Pago no responde (red, 5xx,
    token que no se puede renovar) o la rechaza, avisa con PagosNoDisponibles (503) en vez de un error 500.
    """
    try:
        sdk = _sdk(access_token_de(garaje))  # GarajeSinMercadoPago (409) si el garaje no conectó su cuenta
        result = sdk.preference().create(datos)
    except GarajeSinMercadoPago:
        raise
    except Exception as error:  # red caída, timeout, renovación del token fallida
        logger.exception("Mercado Pago no respondió al crear %s: %s", que, error)
        raise PagosNoDisponibles(detalle_error)
    if result["status"] >= 400:
        logger.error("Mercado Pago rechazó %s (HTTP %s): %s", que, result["status"], result["response"])
        raise PagosNoDisponibles(detalle_error)
    return result["response"]["init_point"]


def crear_preferencia(reserva, canal=CANAL_WEB) -> str:
    """
    Crea una preferencia de Checkout Pro en la cuenta del garaje (POST /checkout/preferences con su token OAuth)
    y devuelve init_point. MP acredita el pago al garaje y le transfiere a Drivly el marketplace_fee.
    """
    preference_data = {
        "items": [{
            "title": f"Reserva Drivly · {reserva.garaje.nombre}",
            "quantity": 1,
            "unit_price": float(reserva.monto),
            "currency_id": "ARS",
        }],
        **_retorno(canal),
        "external_reference": str(reserva.id),
        "marketplace_fee": float(calcular_comision(reserva.monto)),
        "notification_url": f"{settings.BACKEND_URL}/api/pagos/webhook/",
        "statement_descriptor": "DRIVLY",
        # La preferencia vence junto con el hold: pasado ese momento MP no deja pagar.
        "expires": True,
        "expiration_date_from": _fecha_mp(timezone.now()),
        "expiration_date_to": _fecha_mp(reserva.hold_expira),
        # Efectivo (Rapipago, Pago Fácil) se acredita en horas o días: no sirve para un hold de 5 minutos.
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
    }

    init_point = _abrir_checkout(reserva.garaje, preference_data, f"la preferencia de la reserva {reserva.id}")
    Reserva.objects.filter(pk=reserva.pk).update(checkout_en=timezone.now())
    # MP ya no tiene sandbox: las pruebas usan usuarios de prueba con el mismo init_point.
    return init_point


def crear_cobro_deuda(deuda, canal=None) -> str:
    """
    Cobro del overstay en la cuenta del garaje: devuelve el init_point que el playero muestra como QR
    o, con `canal`, el que abre el conductor desde su cuenta (CU-09) y lo trae de vuelta al terminar.
    La deuda es del garaje (regla 4); la comisión se calcula sobre lo cobrado y sólo existe si el pago se concreta.
    """
    garaje = deuda.reserva.garaje
    init_point = _abrir_checkout(garaje, {
        "items": [{
            "title": f"Exceso de permanencia · {garaje.nombre}",
            "quantity": 1,
            "unit_price": float(deuda.monto),
            "currency_id": "ARS",
        }],
        **(_retorno(canal) if canal else {}),
        "external_reference": f"{PREFIJO_DEUDA}{deuda.reserva_id}",
        "marketplace_fee": float(calcular_comision(deuda.monto)),
        "notification_url": f"{settings.BACKEND_URL}/api/pagos/webhook/",
        "statement_descriptor": "DRIVLY",
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
    }, f"el cobro de la deuda de la reserva {deuda.reserva_id}",
        "Mercado Pago no responde en este momento. Probá de nuevo en unos minutos o pagale al garaje en persona.")
    Deuda.objects.filter(pk=deuda.pk).update(checkout_en=timezone.now())
    return init_point


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

    referencia = str(payment.get("external_reference") or "")
    es_deuda = referencia.startswith(PREFIJO_DEUDA)
    try:
        reserva = Reserva.objects.filter(pk=referencia.removeprefix(PREFIJO_DEUDA)).first()
    except ValidationError:  # external_reference que no es un UUID
        reserva = None
    deuda = Deuda.objects.filter(reserva=reserva).first() if reserva and es_deuda else None
    if reserva is None or (es_deuda and deuda is None):
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
                      "comision": calcular_comision(deuda.monto if deuda else reserva.monto)},
        )
        pago.estado_mp = payment.get("status", "")
        pago.estado_detalle_mp = payment.get("status_detail") or ""
        pago.datos_mp = payment
        pago.save()

        if pago.estado_mp != "approved" or pago.resultado not in RESULTADOS_A_PROCESAR:
            return pago

        esperado = deuda.monto if deuda else reserva.monto
        if deuda and deuda.monto_condonado and pago.monto > esperado:  # checkout abierto antes de la condonación
            logger.warning("Pago %s de una deuda condonada (reserva %s): se reembolsa.", pago.payment_id, reserva.id)
            _reembolsar(pago, sdk)
            return pago

        if pago.monto != esperado or payment.get("currency_id") != "ARS":
            logger.error("Pago %s: pagó %s %s y la reserva %s debía %s ARS. No se confirma.",
                         pago.payment_id, pago.monto, payment.get("currency_id"), reserva.id, esperado)
            pago.resultado = ResultadoPago.MONTO_INCORRECTO
            pago.save(update_fields=["resultado", "actualizado_en"])
            return pago

        if deuda:
            if saldar_deuda(reserva.id, MedioCobro.MERCADO_PAGO, pago.payment_id):
                pago.resultado = ResultadoPago.SALDO_DEUDA
                pago.save(update_fields=["resultado", "actualizado_en"])
            else:  # ya la había cobrado el playero en efectivo, o el garaje la condonó
                logger.warning("Pago %s de una deuda ya saldada (reserva %s): se reembolsa.", pago.payment_id, reserva.id)
                _reembolsar(pago, sdk)
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
        from notificaciones.services import disparar

        disparar("reembolso", pago.id)
    pago.save(update_fields=["resultado", "reembolso_id", "actualizado_en"])


# ---------- Reembolsos fuera del webhook ----------

def reembolsar_cancelacion(reserva):
    """
    Reembolso total del pago de una reserva que el conductor canceló. Devuelve el Pago, o None si la reserva
    no tiene un pago aprobado (p. ej. con pagos simulados). Si falla queda REEMBOLSO_FALLIDO y lo retoma
    reintentar_reembolsos.
    """
    with transaction.atomic():
        pago = Pago.objects.select_for_update().filter(
            reserva=reserva, resultado=ResultadoPago.CONFIRMO_RESERVA
        ).first()
        if pago is None:
            return None
        _reembolsar_con_cuenta_del_garaje(pago, reserva.garaje)
    return pago


def _reembolsar_con_cuenta_del_garaje(pago, garaje):
    try:
        sdk = _sdk(access_token_de(garaje))
    except GarajeSinMercadoPago:
        logger.error("No se puede reembolsar el pago %s: el garaje %s perdió la conexión con MP",
                     pago.payment_id, garaje.pk)
        pago.resultado = ResultadoPago.REEMBOLSO_FALLIDO
        pago.save(update_fields=["resultado", "actualizado_en"])
        return
    _reembolsar(pago, sdk)


def reintentar_reembolsos() -> int:
    """Tarea periódica: reintenta los reembolsos fallidos de reservas que ya no se van a confirmar."""
    reembolsados = 0
    for pago_id in Pago.objects.filter(resultado=ResultadoPago.REEMBOLSO_FALLIDO).values_list("pk", flat=True):
        with transaction.atomic():
            pago = Pago.objects.select_for_update().select_related("reserva__garaje").get(pk=pago_id)
            # Otro proceso pudo resolverlo, o el webhook pudo confirmar la reserva si se liberó un lugar.
            if pago.resultado != ResultadoPago.REEMBOLSO_FALLIDO or pago.reserva.estado == EstadoReserva.CONFIRMADA:
                continue
            _reembolsar_con_cuenta_del_garaje(pago, pago.reserva.garaje)
            reembolsados += pago.resultado == ResultadoPago.REEMBOLSADO
    return reembolsados


# ---------- Conciliación: pagos cuyo aviso no llegó ----------

# El webhook suele llegar en segundos: recién después de esta espera se le pregunta a Mercado Pago
ESPERA_WEBHOOK = timedelta(minutes=5)
# Un pago con tarjeta puede quedar en revisión y aprobarse horas después
VENTANA_CONCILIACION = timedelta(hours=24)


def _pagos_aprobados(garaje, referencia):
    """Busca en la cuenta del garaje los pagos aprobados con ese external_reference (GET /v1/payments/search)."""
    sdk = _sdk(access_token_de(garaje))
    respuesta = sdk.payment().search({"external_reference": referencia, "status": "approved"})
    if respuesta["status"] >= 400:
        raise RuntimeError(f"Error buscando los pagos de {referencia}: {respuesta['response']}")
    return [str(p["id"]) for p in respuesta["response"].get("results", [])]


def conciliar_pagos() -> int:
    """
    Tarea periódica. Si Mercado Pago estuvo caído (o el webhook no llegó) puede haber pagos aprobados que Drivly no
    registró: el conductor pagó y su reserva sigue retenida o venció. Para cada checkout abierto en las últimas 24 h
    sin un pago aprobado registrado, busca el pago en Mercado Pago y lo procesa igual que el webhook (confirma la
    reserva, salda la deuda o reembolsa si ya no hay lugar). Devuelve cuántos pagos recuperó.
    """
    ahora = timezone.now()
    rango = (ahora - VENTANA_CONCILIACION, ahora - ESPERA_WEBHOOK)
    reservas = (
        Reserva.objects.filter(estado__in=[EstadoReserva.HOLD, EstadoReserva.EXPIRADA], checkout_en__range=rango)
        .exclude(pagos__estado_mp="approved").select_related("garaje")
    )
    deudas = Deuda.objects.filter(estado=EstadoDeuda.PENDIENTE, checkout_en__range=rango).select_related("reserva__garaje")
    pendientes = [(r.garaje, str(r.id)) for r in reservas]
    pendientes += [(d.reserva.garaje, f"{PREFIJO_DEUDA}{d.reserva_id}") for d in deudas]

    recuperados = 0
    for garaje, referencia in pendientes:
        try:
            mp_user_id = ConexionMP.objects.filter(garaje=garaje).values_list("mp_user_id", flat=True).first()
            for payment_id in _pagos_aprobados(garaje, referencia):
                if Pago.objects.filter(payment_id=payment_id).exclude(resultado__in=RESULTADOS_A_PROCESAR).exists():
                    continue  # ya procesado
                if procesar_notificacion_pago(payment_id, mp_user_id) is not None:
                    recuperados += 1
                    logger.warning("Conciliación: se recuperó el pago %s (%s) sin aviso de Mercado Pago.",
                                   payment_id, referencia)
        except Exception:  # Mercado Pago sigue caído o el garaje se desconectó: se reintenta en la próxima vuelta
            logger.exception("Conciliación: no se pudo consultar %s", referencia)
    return recuperados
