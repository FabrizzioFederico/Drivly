"""
Reglas 1 y 2 de la documentación: control de capacidad con transacciones ACID y hold de 5 minutos.

Concurrencia: crear_hold bloquea la fila del garaje (SELECT ... FOR UPDATE). Dos solicitudes
para el mismo garaje se serializan; para garajes distintos no se bloquean entre sí.
"""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from garajes.models import Garaje, Tarifa
from vehiculos.models import Vehiculo

from .disponibilidad import cercanos_a, que_pueden_cobrar
from .exceptions import (
    DeudaPendiente,
    EstadoInvalido,
    GarajeSinMercadoPago,
    HoldVencidoSinCupo,
    SinCupo,
    SinCupoAbonos,
    SinTarifa,
    VehiculoOcupado,
    VehiculoSinCategoria,
)
from .models import ESTADOS_OCUPAN, MODALIDADES_ABONO, EstadoReserva, Modalidad, Reserva
from .ocupacion import lugares_libres
from .periodos import fin_de_abono

MAX_HORA = timedelta(hours=24)
TOLERANCIA_INICIO = timedelta(minutes=5)  # se puede reservar "ahora" aunque el reloj del celular difiera


def tiene_deuda(conductor) -> bool:
    return Reserva.objects.filter(conductor=conductor, estado=EstadoReserva.CON_DEUDA).exists()


def _validar_intervalo(modalidad, inicio, fin, ahora):
    if inicio < ahora - TOLERANCIA_INICIO:
        raise ValidationError({"inicio": "El inicio no puede estar en el pasado."})
    if modalidad in MODALIDADES_ABONO:
        return inicio, fin_de_abono(inicio, modalidad)
    if fin is None:
        raise ValidationError({"fin": "Obligatorio para reservas por hora."})
    if fin <= inicio:
        raise ValidationError({"fin": "Debe ser posterior al inicio."})
    if fin - inicio > MAX_HORA:
        raise ValidationError({"fin": "Una reserva por hora dura como máximo 24 h. Para más tiempo usá un abono."})
    return inicio, fin


def desglose(tarifa: Tarifa, inicio, fin) -> dict:
    total = tarifa.cotizar(inicio, fin)
    if tarifa.modalidad != Modalidad.HORA:
        return {"modalidad": tarifa.modalidad, "precio_periodo": tarifa.precio_periodo, "subtotal": total,
                "cargo_servicio": 0, "total": total}
    minutos = -(-int((fin - inicio).total_seconds()) // 60)
    fracciones = tarifa.fracciones(minutos)
    return {
        "modalidad": Modalidad.HORA, "precio_fraccion": tarifa.precio_fraccion, "fraccion_min": tarifa.fraccion_min,
        "fracciones": fracciones, "minimo_fracciones": tarifa.minimo_fracciones,
        "minimo_aplicado": fracciones > -(-minutos // tarifa.fraccion_min),
        # La comisión de Drivly la paga el garaje vía split de Mercado Pago: el conductor no paga cargo extra.
        "subtotal": total, "cargo_servicio": 0, "total": total,
    }


@transaction.atomic
def crear_hold(conductor, garaje_id, vehiculo_id, modalidad, inicio, fin=None):
    """CU-04 pasos 2 y 3. Devuelve (reserva, desglose)."""
    ahora = timezone.now()
    try:
        garaje = Garaje.objects.select_for_update().get(pk=garaje_id, activo=True)  # serializa por garaje
    except Garaje.DoesNotExist:
        raise NotFound("El garaje no existe o no está disponible.")
    if not que_pueden_cobrar(Garaje.objects.filter(pk=garaje.pk)).exists():
        raise GarajeSinMercadoPago()  # no se retiene un lugar que después no se va a poder pagar
    try:
        vehiculo = conductor.vehiculos.get(pk=vehiculo_id)
    except Vehiculo.DoesNotExist:
        raise ValidationError({"vehiculo": "Elegí uno de tus vehículos."})

    if tiene_deuda(conductor):
        raise DeudaPendiente()
    if not vehiculo.validado:
        raise VehiculoSinCategoria()
    inicio, fin = _validar_intervalo(modalidad, inicio, fin, ahora)

    if Reserva.objects.filter(
        vehiculo=vehiculo, estado__in=ESTADOS_OCUPAN, periodo__overlap=DateTimeTZRange(inicio, fin)
    ).exclude(estado=EstadoReserva.HOLD, hold_expira__lte=ahora).exists():
        raise VehiculoOcupado()

    tarifa = garaje.tarifas.filter(categoria=vehiculo.categoria, modalidad=modalidad).first()
    if tarifa is None:
        raise SinTarifa()

    if lugares_libres(garaje, inicio, fin, modalidad, ahora) <= 0:
        error = SinCupoAbonos if modalidad in MODALIDADES_ABONO else SinCupo
        raise error(cercanos=_cercanos_serializables(garaje, inicio, fin, modalidad))

    detalle = desglose(tarifa, inicio, fin)
    reserva = Reserva.objects.create(
        conductor=conductor, garaje=garaje, vehiculo=vehiculo, modalidad=modalidad,
        periodo=DateTimeTZRange(inicio, fin), estado=EstadoReserva.HOLD,
        hold_expira=ahora + settings.DRIVLY_HOLD_TTL, monto=detalle["total"],
        categoria_cobrada=vehiculo.categoria,
    )
    return reserva, detalle


def cotizar(conductor, garaje_id, vehiculo_id, modalidad, inicio, fin=None):
    """
    Precio que tendría la reserva, sin retener el lugar: la app lo muestra antes de que el conductor
    toque "Retener". Mismas validaciones de vehículo, intervalo y tarifa que crear_hold; el monto final
    se congela recién al crear el hold (regla 3), así que esto es una estimación.
    Devuelve (inicio, fin, desglose).
    """
    garaje = Garaje.objects.filter(pk=garaje_id, activo=True).first()
    if garaje is None:
        raise NotFound("El garaje no existe o no está disponible.")
    try:
        vehiculo = conductor.vehiculos.get(pk=vehiculo_id)
    except Vehiculo.DoesNotExist:
        raise ValidationError({"vehiculo": "Elegí uno de tus vehículos."})
    if not vehiculo.validado:
        raise VehiculoSinCategoria()
    inicio, fin = _validar_intervalo(modalidad, inicio, fin, timezone.now())
    tarifa = garaje.tarifas.filter(categoria=vehiculo.categoria, modalidad=modalidad).first()
    if tarifa is None:
        raise SinTarifa()
    return inicio, fin, desglose(tarifa, inicio, fin)


def _cercanos_serializables(garaje, inicio, fin, modalidad):
    from .serializers import GarajeDisponibleSerializer  # evita import circular

    return GarajeDisponibleSerializer(cercanos_a(garaje, inicio, fin, modalidad), many=True).data


# ---------- QR estático y firmado (RFM-09: funciona sin señal) ----------

_firmador = signing.Signer(salt="drivly.qr", sep=".")
PREFIJO_QR = "drivly.v1."


def generar_qr_token(reserva) -> str:
    return PREFIJO_QR + _firmador.sign(str(reserva.id))


def reserva_desde_qr(token: str):
    """Valida la firma y devuelve la reserva. Lo usa el playero en ingreso y egreso (Sprint 4)."""
    if not token or not token.startswith(PREFIJO_QR):
        raise ValidationError({"qr_token": "QR inválido."})
    try:
        reserva_id = _firmador.unsign(token[len(PREFIJO_QR):])
    except signing.BadSignature:
        raise ValidationError({"qr_token": "QR inválido: la firma no coincide."})
    reserva = Reserva.objects.filter(pk=reserva_id).first()
    if reserva is None:
        raise NotFound("No existe una reserva con ese QR.")
    return reserva


# ---------- Confirmación, cancelación y expiración ----------

def confirmar_pago(reserva_id):
    """
    Llamado por el webhook de Mercado Pago (Sprint 3) con el pago aprobado. CU-04 paso 7 y alternativa 6b:
      - HOLD vigente -> CONFIRMADA.
      - Hold vencido -> se vuelve a verificar el cupo bajo bloqueo; si no hay lugar queda EXPIRADA y se
        lanza HoldVencidoSinCupo (el webhook pide el reembolso).
    Idempotente: confirmar dos veces la misma reserva no hace nada nuevo.
    """
    reserva, confirmada = _confirmar(reserva_id)
    if not confirmada:  # se lanza fuera de la transacción para que el cambio a EXPIRADA quede guardado
        raise HoldVencidoSinCupo()
    return reserva


@transaction.atomic
def _confirmar(reserva_id):
    ahora = timezone.now()
    garaje_id = Reserva.objects.values_list("garaje_id", flat=True).get(pk=reserva_id)
    garaje = Garaje.objects.select_for_update().get(pk=garaje_id)
    reserva = Reserva.objects.select_for_update().get(pk=reserva_id)
    if reserva.estado == EstadoReserva.CONFIRMADA:
        return reserva, True
    if reserva.estado not in (EstadoReserva.HOLD, EstadoReserva.EXPIRADA):
        raise EstadoInvalido(f"No se puede confirmar una reserva {reserva.get_estado_display().lower()}.")
    if reserva.hold_expira <= ahora and lugares_libres(
        garaje, reserva.inicio, reserva.fin, reserva.modalidad, ahora, excluir_id=reserva.id
    ) <= 0:
        reserva.estado = EstadoReserva.EXPIRADA
        reserva.save(update_fields=["estado"])
        return reserva, False
    reserva.estado = EstadoReserva.CONFIRMADA
    reserva.qr_token = generar_qr_token(reserva)
    reserva.confirmada_en = ahora
    reserva.save(update_fields=["estado", "qr_token", "confirmada_en"])
    return reserva, True


def cancelable_hasta(reserva):
    """
    Último momento en que una reserva confirmada se puede cancelar con reembolso total (None si no aplica):
    hasta DRIVLY_CANCELACION_ANTICIPACION antes del inicio, o dentro de DRIVLY_CANCELACION_GRACIA desde el pago
    (lo que sea más tarde). La gracia cubre a quien reserva sobre la hora, pero nunca pasa del inicio.
    """
    if reserva.estado != EstadoReserva.CONFIRMADA:
        return None
    limite = reserva.inicio - settings.DRIVLY_CANCELACION_ANTICIPACION
    if reserva.confirmada_en:
        limite = max(limite, min(reserva.confirmada_en + settings.DRIVLY_CANCELACION_GRACIA, reserva.inicio))
    return limite


def _minutos(duracion):
    minutos = int(duracion.total_seconds() // 60)
    return f"{minutos // 60} h" if minutos % 60 == 0 else f"{minutos} min"


@transaction.atomic
def cancelar(reserva):
    """
    Libera un hold, o cancela una reserva confirmada hasta DRIVLY_CANCELACION_ANTICIPACION antes del inicio.
    El reembolso del pago lo hace pagos.services.reembolsar_cancelacion (este módulo no conoce Mercado Pago).
    """
    reserva = Reserva.objects.select_for_update().get(pk=reserva.pk)
    if reserva.estado == EstadoReserva.HOLD:
        pass
    elif reserva.estado == EstadoReserva.CONFIRMADA and timezone.now() <= cancelable_hasta(reserva) \
            and reserva.inicio > timezone.now():
        pass
    elif reserva.estado == EstadoReserva.CONFIRMADA and reserva.inicio > timezone.now():
        raise EstadoInvalido(
            f"Las reservas se pueden cancelar hasta {_minutos(settings.DRIVLY_CANCELACION_ANTICIPACION)} antes "
            f"del inicio, o en los {_minutos(settings.DRIVLY_CANCELACION_GRACIA)} siguientes al pago."
        )
    else:
        raise EstadoInvalido("Sólo se puede cancelar un hold o una reserva confirmada que todavía no empezó.")
    reserva.estado = EstadoReserva.CANCELADA
    reserva.save(update_fields=["estado"])
    return reserva


def expirar_holds(ahora=None) -> int:
    """
    Limpieza física (regla 2, capa 2). El cupo ya se liberó en el instante del vencimiento
    porque `ocupantes` ignora holds vencidos; esto sólo deja el historial correcto.
    """
    ahora = ahora or timezone.now()
    return Reserva.objects.filter(estado=EstadoReserva.HOLD, hold_expira__lte=ahora).update(
        estado=EstadoReserva.EXPIRADA
    )
