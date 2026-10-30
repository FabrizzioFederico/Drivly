"""
Operación del garaje: ingreso (CU-07), egreso y overstay (CU-08, regla 4), presenciales y "sin lugar" (regla 6).
La hora de ingreso y egreso la fija siempre el servidor, nunca el dispositivo del playero.
"""
import logging
import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from garajes.models import Garaje
from reservas.disponibilidad import cercanos_a
from reservas.exceptions import DeudaPatente, DeudaPendiente, EstadoInvalido, SinLugarPresencial
from reservas.models import EstadoReserva, Modalidad, Reserva
from reservas.ocupacion import lugares_libres
from reservas.serializers import GarajeDisponibleSerializer
from reservas.services import reserva_desde_qr, tiene_deuda
from vehiculos.models import Categoria, es_patente_de_moto

from .models import (
    ESTADOS_IMPAGOS, Deuda, EstadoDeuda, Incidente, MedioCobro, Movimiento, TipoIncidente, TipoMovimiento,
)

logger = logging.getLogger(__name__)


def cercanos_serializados(garaje, inicio, fin, modalidad=Modalidad.HORA, categoria=None):
    return GarajeDisponibleSerializer(cercanos_a(garaje, inicio, fin, modalidad, categoria), many=True).data


def _reserva_por_qr(garaje, token):
    """Valida la firma y que el QR sea de este garaje (CU-08 2a). Devuelve la reserva bloqueada."""
    reserva_id = reserva_desde_qr(token).pk
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    if reserva.garaje_id != garaje.id:
        raise ValidationError({"qr_token": "Este QR es de otro garaje."})
    return reserva


def _reserva_adentro_por_patente(garaje, patente):
    reserva = (
        Reserva.objects.select_for_update()
        .filter(garaje=garaje, estado=EstadoReserva.EN_CURSO)
        .filter(id__in=_ids_con_patente(patente))
        .first()
    )
    if reserva is None:
        raise NotFound("No hay ningún vehículo con esa patente adentro del garaje.")
    return reserva


def _ids_con_patente(patente):
    return Reserva.objects.filter(Q(patente_presencial=patente) | Q(vehiculo__patente=patente)).values("id")


def _exigir_patente_sin_deuda(patente):
    """Pasado el bloqueo la deuda sigue al vehículo (CP-30): no alcanza con entrar con otra cuenta o sin reserva."""
    deuda = (
        Deuda.objects.select_related("reserva__garaje")
        .filter(patente=patente, estado__in=ESTADOS_IMPAGOS, vence_bloqueo__lte=timezone.now())
        .order_by("egreso_real")
        .first()
    )
    if deuda:
        raise DeudaPatente(deuda=deuda)


# ---------- Ingreso ----------

@transaction.atomic
def ingreso_con_qr(garaje, token, usuario):
    """CU-07. Un abono entra y sale muchas veces: vuelve a CONFIRMADA en cada egreso dentro de su período."""
    reserva = _reserva_por_qr(garaje, token)
    if reserva.estado != EstadoReserva.CONFIRMADA:
        raise EstadoInvalido(f"La reserva está {reserva.get_estado_display().lower()} y no habilita el ingreso.")
    _exigir_patente_sin_deuda(reserva.patente)
    if reserva.conductor_id and tiene_deuda(reserva.conductor):  # abono suspendido por deuda (CP-31)
        raise DeudaPendiente("El conductor tiene una deuda pendiente: debe saldarla antes de ingresar.")
    ahora = timezone.now()
    if ahora >= reserva.fin:
        raise EstadoInvalido("La reserva ya venció y no habilita el ingreso.")
    if ahora < reserva.inicio - timedelta(minutes=garaje.tolerancia_min):
        hora = timezone.localtime(reserva.inicio).strftime("%H:%M")
        raise EstadoInvalido(f"Todavía no es la hora de la reserva: empieza a las {hora}.")
    reserva.estado = EstadoReserva.EN_CURSO
    reserva.save(update_fields=["estado"])
    Movimiento.objects.create(reserva=reserva, tipo=TipoMovimiento.INGRESO, registrado_por=usuario)
    return reserva


@transaction.atomic
def ingreso_presencial(garaje, patente, salida_estimada, usuario):
    """
    Regla 6: entra sólo si hay lugar hasta la salida estimada, contando las reservas de la app que llegan
    en ese lapso. El bloqueo del garaje lo serializa con crear_hold para que no se pisen.
    """
    garaje = Garaje.objects.select_for_update().get(pk=garaje.pk)
    ahora = timezone.now()
    if salida_estimada <= ahora:
        raise ValidationError({"salida_estimada": "Debe ser posterior a este momento."})
    if Reserva.objects.filter(garaje=garaje, estado=EstadoReserva.EN_CURSO, id__in=_ids_con_patente(patente)).exists():
        raise EstadoInvalido("Ese vehículo ya está adentro del garaje.")
    _exigir_patente_sin_deuda(patente)
    if lugares_libres(garaje, ahora, salida_estimada, Modalidad.PRESENCIAL, ahora) <= 0:
        raise SinLugarPresencial(cercanos=cercanos_serializados(garaje, ahora, salida_estimada))
    reserva = Reserva.objects.create(
        garaje=garaje, modalidad=Modalidad.PRESENCIAL, estado=EstadoReserva.EN_CURSO,
        periodo=DateTimeTZRange(ahora, salida_estimada), salida_estimada=salida_estimada,
        patente_presencial=patente,
        categoria_cobrada=Categoria.MOTO if es_patente_de_moto(patente) else Categoria.AUTO,
    )
    Movimiento.objects.create(reserva=reserva, tipo=TipoMovimiento.INGRESO, registrado_por=usuario)
    return reserva


# ---------- Egreso y overstay ----------

def _tarifa_hora(reserva):
    # Un abono no tiene precio por fracción: su overstay se cobra con la tarifa por hora de la categoría.
    return reserva.garaje.tarifas.filter(categoria=reserva.categoria_cobrada, modalidad=Modalidad.HORA).first()


def calcular_deuda(reserva, egreso):
    """Regla 4: ⌈(egreso - fin - tolerancia) / fracción⌉ × precio_fracción × (1 + recargo). None si no excedió."""
    garaje = reserva.garaje
    excedido = (egreso - reserva.fin - timedelta(minutes=garaje.tolerancia_min)).total_seconds()
    if excedido <= 0:
        return None
    tarifa = _tarifa_hora(reserva)
    if tarifa is None:  # no se le impide salir al auto por un error de configuración del garaje
        logger.error("Overstay de la reserva %s sin tarifa por hora para cobrarlo", reserva.id)
        return None
    fracciones = math.ceil(excedido / (tarifa.fraccion_min * 60))
    monto = (fracciones * tarifa.precio_fraccion * (1 + garaje.recargo_overstay)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return Deuda(
        reserva=reserva, patente=reserva.patente, egreso_real=egreso, minutos_excedidos=math.ceil(excedido / 60),
        tolerancia_min=garaje.tolerancia_min, fraccion_min=tarifa.fraccion_min, fracciones=fracciones,
        precio_fraccion=tarifa.precio_fraccion, recargo=garaje.recargo_overstay, monto=monto,
        vence_bloqueo=egreso + settings.DRIVLY_DEUDA_BLOQUEO,
    )


def _cerrar_presencial(reserva, egreso):
    """El presencial paga lo que realmente estuvo, no lo estimado."""
    reserva.periodo = DateTimeTZRange(reserva.inicio, egreso)
    tarifa = _tarifa_hora(reserva)
    if tarifa is None:
        logger.error("Presencial %s sin tarifa por hora: egresa con importe 0", reserva.id)
    else:
        reserva.monto = tarifa.cotizar(reserva.inicio, egreso)
    reserva.estado = EstadoReserva.FINALIZADA


@transaction.atomic
def egreso(garaje, usuario, token=None, patente=None):
    """CU-08. Devuelve (reserva, deuda o None)."""
    reserva = _reserva_por_qr(garaje, token) if token else _reserva_adentro_por_patente(garaje, patente)
    if reserva.estado != EstadoReserva.EN_CURSO:
        raise EstadoInvalido(f"La reserva está {reserva.get_estado_display().lower()}: no hay egreso que registrar.")
    ahora = timezone.now()
    deuda = None
    if reserva.modalidad == Modalidad.PRESENCIAL:
        _cerrar_presencial(reserva, ahora)
    elif reserva.es_abono and ahora < reserva.fin:
        reserva.estado = EstadoReserva.CONFIRMADA  # sale pero conserva su lugar y su QR
    else:
        deuda = calcular_deuda(reserva, ahora)
        reserva.estado = EstadoReserva.CON_DEUDA if deuda else EstadoReserva.FINALIZADA
    reserva.save(update_fields=["estado", "periodo", "monto"])
    if deuda:
        deuda.save()
    Movimiento.objects.create(reserva=reserva, tipo=TipoMovimiento.EGRESO, registrado_por=usuario)
    return reserva, deuda


@transaction.atomic
def saldar_deuda(reserva_id, medio, transaccion_id=""):
    """Devuelve True si esta llamada la saldó, False si ya no se debía. Libera la cuenta del conductor."""
    deuda = Deuda.objects.select_for_update().get(reserva_id=reserva_id)
    if deuda.estado not in ESTADOS_IMPAGOS:
        return False
    deuda.estado = EstadoDeuda.PAGADA
    deuda.medio = medio
    deuda.transaccion_id = transaccion_id
    deuda.pagada_en = timezone.now()
    deuda.save(update_fields=["estado", "medio", "transaccion_id", "pagada_en"])
    Reserva.objects.filter(pk=reserva_id, estado=EstadoReserva.CON_DEUDA).update(estado=EstadoReserva.FINALIZADA)
    return True


def registrar_efectivo(deuda):
    return saldar_deuda(deuda.reserva_id, MedioCobro.EFECTIVO)


@transaction.atomic
def condonar_deuda(reserva_id, motivo, monto=None):
    """
    Reclamo del conductor (regla 4). Sin `monto`, o con todo el saldo, es total y libera la cuenta;
    con menos, baja el saldo y la cuenta sigue suspendida hasta pagar el resto.
    """
    deuda = Deuda.objects.select_for_update().get(reserva_id=reserva_id)
    if deuda.estado not in ESTADOS_IMPAGOS:
        raise EstadoInvalido("Esa deuda ya no está pendiente.")
    if monto is not None and monto > deuda.monto:
        raise ValidationError({"monto": "No puede superar el saldo de la deuda."})
    parcial = monto is not None and monto < deuda.monto
    deuda.monto_condonado += monto if parcial else deuda.monto
    deuda.motivo_condonacion = "\n".join(filter(None, [deuda.motivo_condonacion, motivo]))
    if parcial:
        deuda.monto -= monto
    else:
        deuda.estado = EstadoDeuda.CONDONADA
        Reserva.objects.filter(pk=reserva_id, estado=EstadoReserva.CON_DEUDA).update(estado=EstadoReserva.FINALIZADA)
    deuda.save(update_fields=["monto", "monto_condonado", "motivo_condonacion", "estado"])
    return deuda


# ---------- Tareas programadas de la deuda impaga ----------

def _enviar_recordatorio(deuda):
    conductor = deuda.reserva.conductor
    garaje = deuda.reserva.garaje
    send_mail(
        subject=f"Drivly: tenés una deuda pendiente en {garaje.nombre}",
        message=(
            f"Hola{(' ' + conductor.nombre) if conductor.nombre else ''}:\n\n"
            f"Tu vehículo {deuda.patente} salió de {garaje.nombre} {deuda.minutos_excedidos} minutos después "
            f"del horario reservado y quedó una deuda de ${deuda.monto}.\n\n"
            "Mientras no la saldes no podés hacer reservas nuevas y tus abonos quedan suspendidos. "
            "Podés pagarla desde Mis reservas, en la app.\n\n"
            "Si ya la pagaste, ignorá este mensaje."
        ),
        from_email=None,
        recipient_list=[conductor.email],
    )


def recordar_deudas() -> int:
    """
    Recordatorios a las 0, 24 y 48 h. Si la tarea estuvo parada y venció más de uno se manda uno solo.
    Un mail que falla no cuenta como enviado: se reintenta en la próxima corrida.
    """
    hitos = settings.DRIVLY_DEUDA_RECORDATORIOS
    ahora = timezone.now()
    enviados = 0
    pendientes = Deuda.objects.filter(estado=EstadoDeuda.PENDIENTE, recordatorios_enviados__lt=len(hitos))
    for deuda_id in pendientes.values_list("pk", flat=True):
        with transaction.atomic():
            deuda = (
                Deuda.objects.select_for_update(of=("self",))
                .select_related("reserva__garaje", "reserva__conductor")
                .get(pk=deuda_id)
            )
            vencidos = sum(deuda.egreso_real + hito <= ahora for hito in hitos)
            if deuda.estado != EstadoDeuda.PENDIENTE or vencidos <= deuda.recordatorios_enviados:
                continue
            try:
                _enviar_recordatorio(deuda)
            except Exception:
                logger.exception("No se pudo enviar el recordatorio de la deuda de la reserva %s", deuda.reserva_id)
                continue
            deuda.recordatorios_enviados = vencidos
            deuda.save(update_fields=["recordatorios_enviados"])
            enviados += 1
    return enviados


def marcar_incobrables() -> int:
    """CP-32: sólo cambia para los reportes. La reserva sigue CON_DEUDA y la cuenta, suspendida."""
    limite = timezone.now() - settings.DRIVLY_DEUDA_INCOBRABLE
    return Deuda.objects.filter(estado=EstadoDeuda.PENDIENTE, egreso_real__lte=limite).update(
        estado=EstadoDeuda.INCOBRABLE
    )


# ---------- Sin lugar físico ----------

@transaction.atomic
def marcar_sin_lugar(garaje, token, usuario):
    """Regla 6. El reembolso lo pide la vista después de confirmar el estado, igual que al cancelar."""
    reserva = _reserva_por_qr(garaje, token)
    if reserva.estado != EstadoReserva.CONFIRMADA:
        raise EstadoInvalido("Sólo se puede marcar sin lugar una reserva confirmada que todavía no ingresó.")
    reserva.estado = EstadoReserva.SIN_LUGAR
    reserva.save(update_fields=["estado"])
    Incidente.objects.create(garaje=garaje, reserva=reserva, tipo=TipoIncidente.SIN_LUGAR, registrado_por=usuario)
    return reserva
