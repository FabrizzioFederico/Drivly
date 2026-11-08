"""
Avisos al conductor: comprobantes por email y notificaciones push.

Cada aviso se registra en `Aviso` antes de mandarlo, así un mismo comprobante sale una sola vez aunque
Mercado Pago notifique el pago varias veces. Si el envío falla, el registro se borra y la tarea lo reintenta.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from . import push
from .models import Aviso, Canal

logger = logging.getLogger(__name__)

INICIO_PROXIMO = timedelta(minutes=30)
FIN_PROXIMO = timedelta(minutes=15)


# ---------- Formato ----------

def pesos(monto) -> str:
    """$4.080 o $4.080,50, como se escribe en Argentina."""
    monto = Decimal(str(monto)).quantize(Decimal("0.01"))
    entero, centavos = f"{monto:,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"${entero}" if centavos == "00" else f"${entero},{centavos}"


def fecha_hora(dt) -> str:
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else "—"


def hora(dt) -> str:
    return timezone.localtime(dt).strftime("%H:%M")


def _periodo(reserva) -> str:
    if reserva.es_abono:
        return f"{reserva.get_modalidad_display()} · del {fecha_hora(reserva.inicio)[:10]} al {fecha_hora(reserva.fin)[:10]}"
    return f"{fecha_hora(reserva.inicio)} a {hora(reserva.fin)}"


MEDIOS_MP = {"account_money": "Dinero en cuenta", "credit_card": "Tarjeta de crédito", "debit_card": "Tarjeta de débito"}


def _medio_de(pago) -> str:
    if pago is None:
        return "Mercado Pago"
    tipo = (pago.datos_mp or {}).get("payment_type_id", "")
    return f"Mercado Pago · {MEDIOS_MP[tipo]}" if tipo in MEDIOS_MP else "Mercado Pago"


# ---------- Envío con registro ----------

def una_vez(usuario, tipo: str, clave, canal: str, enviar) -> bool:
    """Registra el aviso y lo manda. Devuelve False si ya se había mandado."""
    try:
        with transaction.atomic():
            aviso = Aviso.objects.create(usuario=usuario, tipo=tipo, clave=str(clave), canal=canal)
    except IntegrityError:
        return False
    try:
        enviar()
    except Exception:
        aviso.delete()  # que la tarea lo reintente
        raise
    return True


def cada_canal(*envios):
    """
    Manda el email y el push por separado: si falla uno (p. ej. el SMTP), el otro sale igual.
    Después relanza el primer error para que la tarea reintente; lo que ya salió no se repite (una_vez).
    """
    errores = []
    for enviar in envios:
        try:
            enviar()
        except Exception as error:
            logger.warning("Falló un aviso: %s", error)
            errores.append(error)
    if errores:
        raise errores[0]


def _comprobante(usuario, asunto: str, titulo: str, filas: list[tuple[str, str]], total: str, nota: str = ""):
    contexto = {"nombre": usuario.nombre, "titulo": titulo, "filas": filas, "total": total, "nota": nota}
    mensaje = EmailMultiAlternatives(
        subject=asunto,
        body=render_to_string("notificaciones/comprobante.txt", contexto),
        from_email=None,
        to=[usuario.email],
    )
    mensaje.attach_alternative(render_to_string("notificaciones/comprobante.html", contexto), "text/html")
    mensaje.send()


def _filas_reserva(reserva):
    garaje = reserva.garaje
    return [
        ("Garaje", garaje.nombre),
        ("Dirección", garaje.direccion),
        ("CUIT del garaje", garaje.cuit),
        ("Patente", reserva.patente),
        ("Reserva", _periodo(reserva)),
    ]


AVISO_FISCAL = ("Este comprobante no es una factura. La factura de la estadía la emite el garaje, "
                "que es quien presta el servicio.")


# ---------- Eventos ----------

def reserva_confirmada(reserva_id):
    from pagos.models import Pago, ResultadoPago
    from reservas.models import Reserva

    reserva = Reserva.objects.select_related("garaje", "vehiculo", "conductor").get(pk=reserva_id)
    conductor = reserva.conductor
    if conductor is None:  # las reservas presenciales no tienen conductor en la app
        return
    pago = Pago.objects.filter(reserva=reserva, resultado=ResultadoPago.CONFIRMO_RESERVA).first()
    filas = _filas_reserva(reserva) + [
        ("Medio de pago", _medio_de(pago)),
        ("Operación de Mercado Pago", pago.payment_id if pago else "—"),
        ("Fecha del pago", fecha_hora(reserva.confirmada_en)),
    ]
    cuando = (f"desde el {fecha_hora(reserva.inicio)[:10]}" if reserva.es_abono
              else f"el {fecha_hora(reserva.inicio)[:10]} a las {hora(reserva.inicio)}")
    cada_canal(
        lambda: una_vez(conductor, "reserva_confirmada", reserva.id, Canal.EMAIL, lambda: _comprobante(
            conductor, f"Drivly: comprobante de tu reserva en {reserva.garaje.nombre}", "Reserva confirmada",
            filas, pesos(reserva.monto),
            "Mostrá el QR de Mis reservas al llegar. Podés cancelar con reembolso total hasta 2 h antes del inicio. "
            + AVISO_FISCAL,
        )),
        lambda: una_vez(conductor, "reserva_confirmada", reserva.id, Canal.PUSH, lambda: push.enviar(
            conductor, "Reserva confirmada", f"Te esperamos en {reserva.garaje.nombre} {cuando}.",
            {"tipo": "reserva", "reserva_id": reserva.id},
        )),
    )


def deuda_pagada(reserva_id):
    from operacion.models import Deuda, MedioCobro

    deuda = Deuda.objects.select_related("reserva__garaje", "reserva__vehiculo", "reserva__conductor").get(
        reserva_id=reserva_id
    )
    reserva, conductor = deuda.reserva, deuda.reserva.conductor
    if conductor is None:
        return
    medio = "Efectivo, cobrado por el playero" if deuda.medio == MedioCobro.EFECTIVO else "Mercado Pago"
    filas = _filas_reserva(reserva) + [
        ("Concepto", f"Exceso de permanencia de {deuda.minutos_excedidos} min"),
        ("Medio de pago", medio),
        ("Operación de Mercado Pago", deuda.transaccion_id or "—"),
        ("Fecha del pago", fecha_hora(deuda.pagada_en)),
    ]
    cada_canal(
        lambda: una_vez(conductor, "deuda_pagada", reserva.id, Canal.EMAIL, lambda: _comprobante(
            conductor, f"Drivly: comprobante del pago de tu deuda en {reserva.garaje.nombre}", "Deuda saldada",
            filas, pesos(deuda.monto), "Tu cuenta ya puede hacer reservas nuevas. " + AVISO_FISCAL,
        )),
        lambda: una_vez(conductor, "deuda_pagada", reserva.id, Canal.PUSH, lambda: push.enviar(
            conductor, "Deuda saldada", "Ya podés volver a reservar.", {"tipo": "deuda", "reserva_id": reserva.id},
            canal_android="deudas",
        )),
    )


def reembolso(pago_id):
    from pagos.models import Pago

    pago = Pago.objects.select_related("reserva__garaje", "reserva__vehiculo", "reserva__conductor").get(pk=pago_id)
    reserva, conductor = pago.reserva, pago.reserva.conductor
    if conductor is None:
        return
    filas = _filas_reserva(reserva) + [
        ("Pago original", f"Operación {pago.payment_id} de Mercado Pago"),
        ("Reembolso", f"Operación {pago.reembolso_id}" if pago.reembolso_id else "—"),
        ("Fecha", fecha_hora(timezone.now())),
    ]
    cada_canal(
        lambda: una_vez(conductor, "reembolso", pago.id, Canal.EMAIL, lambda: _comprobante(
            conductor, f"Drivly: te devolvimos {pesos(pago.monto)}", "Reembolso", filas, pesos(pago.monto),
            "La devolución se acredita por el mismo medio con que pagaste. Con tarjeta puede tardar hasta el próximo resumen.",
        )),
        lambda: una_vez(conductor, "reembolso", pago.id, Canal.PUSH, lambda: push.enviar(
            conductor, "Reembolso hecho", f"Te devolvimos {pesos(pago.monto)} de tu reserva en {reserva.garaje.nombre}.",
            {"tipo": "reserva", "reserva_id": reserva.id},
        )),
    )


def recordar_inicios() -> int:
    """Push 30 min antes de que empiece una reserva por hora."""
    from reservas.models import EstadoReserva, Modalidad, Reserva

    ahora = timezone.now()
    reservas = Reserva.objects.select_related("garaje", "conductor").filter(
        estado=EstadoReserva.CONFIRMADA, modalidad=Modalidad.HORA, conductor__isnull=False,
        periodo__startswith__gt=ahora, periodo__startswith__lte=ahora + INICIO_PROXIMO,
    )
    enviados = 0
    for r in reservas:
        enviados += una_vez(r.conductor, "inicio_proximo", r.id, Canal.PUSH, lambda r=r: push.enviar(
            r.conductor, f"Tu reserva empieza a las {hora(r.inicio)}",
            f"{r.garaje.nombre}, {r.garaje.direccion}. Tené a mano el QR.", {"tipo": "reserva", "reserva_id": r.id},
        ))
    return enviados


def avisar_fines() -> int:
    """Push 15 min antes del fin de una estadía por hora: después se cobra el exceso con recargo."""
    from reservas.models import EstadoReserva, Modalidad, Reserva

    ahora = timezone.now()
    reservas = Reserva.objects.select_related("garaje", "conductor").filter(
        estado=EstadoReserva.EN_CURSO, modalidad=Modalidad.HORA, conductor__isnull=False,
        periodo__endswith__gt=ahora, periodo__endswith__lte=ahora + FIN_PROXIMO,
    )
    enviados = 0
    for r in reservas:
        enviados += una_vez(r.conductor, "fin_proximo", r.id, Canal.PUSH, lambda r=r: push.enviar(
            r.conductor, f"Tu reserva termina a las {hora(r.fin)}",
            f"Si salís más tarde de {r.garaje.nombre}, se cobra el tiempo extra con recargo.",
            {"tipo": "reserva", "reserva_id": r.id},
        ))
    return enviados


def recordar_deuda_por_push(deuda):
    """Acompaña a cada recordatorio de deuda por email (los manda operacion.services.recordar_deudas)."""
    reserva = deuda.reserva
    if reserva.conductor is None:
        return
    try:
        push.enviar(reserva.conductor, "Tenés una deuda pendiente",
                    f"{pesos(deuda.monto)} en {reserva.garaje.nombre}. Pagala desde Mis reservas para volver a reservar.",
                    {"tipo": "deuda", "reserva_id": reserva.id}, canal_android="deudas")
    except Exception:  # el email ya salió: un push fallido no lo invalida
        logger.exception("No se pudo mandar el push de la deuda de la reserva %s", reserva.id)


# ---------- Disparo desde otros módulos ----------

def disparar(nombre_tarea: str, *args):
    """
    Encola el aviso cuando termina la transacción en curso (si se revierte, no se avisa nada).
    Sin Celery disponible (desarrollo sin Redis) lo manda en el momento: un aviso nunca rompe un pago.
    """
    def encolar():
        from . import tasks

        tarea = getattr(tasks, nombre_tarea)
        try:
            tarea.delay(*map(str, args))
        except Exception:
            logger.warning("Celery no disponible: el aviso %s se manda en el momento", nombre_tarea)
            try:
                tarea.run(*map(str, args))
            except Exception:
                logger.exception("Falló el aviso %s%s", nombre_tarea, args)

    transaction.on_commit(encolar)

