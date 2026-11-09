"""
Caja del garaje: con qué medio pagó cada cliente presencial y el cierre del día que hace el playero.

Plata que pasa por las manos del playero (y tiene que estar en la caja):
  - clientes sin reserva que pagaron en efectivo (o sin medio marcado: se cuentan como efectivo);
  - excesos de permanencia cobrados en efectivo.
Lo demás (Mercado Pago, transferencias, reservas de la app) se informa pero no se cuenta en la caja.
"""
from datetime import datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from garajes.models import Garaje
from reservas.exceptions import EstadoInvalido
from reservas.models import EstadoReserva, Modalidad, Reserva

from .models import CierreCaja, Deuda, EstadoDeuda, MedioCobro

SIN_INDICAR = "SIN_INDICAR"
ESTADOS_SIN_INGRESO = (EstadoReserva.CANCELADA, EstadoReserva.EXPIRADA, EstadoReserva.SIN_LUGAR, EstadoReserva.HOLD)
CERO = Decimal("0.00")


def _total(qs, campo="monto"):
    return (qs.aggregate(t=Sum(campo))["t"] or CERO).quantize(Decimal("0.01"))


def _por_medio(qs, campo_medio):
    """{medio: {"cantidad": n, "total": "123.00"}} con todos los medios, aunque estén en cero."""
    filas = {f[campo_medio] or SIN_INDICAR: f for f in qs.values(campo_medio).annotate(n=Count("pk"), t=Sum("monto"))}
    medios = [m.value for m in MedioCobro] + [SIN_INDICAR]
    return {m: {"cantidad": filas.get(m, {}).get("n", 0), "total": str((filas.get(m, {}).get("t") or CERO))} for m in medios}


def inicio_de_caja(garaje):
    """Desde dónde cuenta el próximo cierre: el último cierre del garaje, o el comienzo del día si nunca cerró."""
    ultimo = garaje.cierres.order_by("-hasta").first()
    if ultimo:
        return ultimo.hasta
    return timezone.make_aware(datetime.combine(timezone.localdate(), time.min))


def resumen(garaje, desde, hasta):
    presenciales = Reserva.objects.filter(
        garaje=garaje, modalidad=Modalidad.PRESENCIAL, estado=EstadoReserva.FINALIZADA,
        periodo__endswith__gte=desde, periodo__endswith__lt=hasta,
    )
    excesos = Deuda.objects.filter(reserva__garaje=garaje, estado=EstadoDeuda.PAGADA, pagada_en__gte=desde, pagada_en__lt=hasta)
    app = Reserva.objects.filter(garaje=garaje, confirmada_en__gte=desde, confirmada_en__lt=hasta).exclude(
        estado__in=ESTADOS_SIN_INGRESO
    ).exclude(modalidad=Modalidad.PRESENCIAL)

    por_medio_presencial = _por_medio(presenciales, "medio_cobro")
    por_medio_excesos = _por_medio(excesos, "medio")
    efectivo = (
        Decimal(por_medio_presencial[MedioCobro.EFECTIVO]["total"])
        + Decimal(por_medio_presencial[SIN_INDICAR]["total"])
        + Decimal(por_medio_excesos[MedioCobro.EFECTIVO]["total"])
    )
    return {
        "desde": desde, "hasta": hasta,
        "efectivo_esperado": str(efectivo.quantize(Decimal("0.01"))),
        "presenciales": por_medio_presencial,
        "excesos": por_medio_excesos,
        "app": {"cantidad": app.count(), "total": str(_total(app))},  # Mercado Pago: no pasa por la caja
    }


def resumen_actual(garaje):
    return resumen(garaje, inicio_de_caja(garaje), timezone.now())


def marcar_medio(garaje, reserva_id, medio):
    """El playero marca con qué pagó un cliente sin reserva. Se puede corregir mientras no entre en un cierre."""
    if medio not in MedioCobro.values:
        raise ValidationError({"medio": "Elegí efectivo, Mercado Pago o transferencia."})
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().filter(
            pk=reserva_id, garaje=garaje, modalidad=Modalidad.PRESENCIAL, estado=EstadoReserva.FINALIZADA
        ).first()
        if reserva is None:
            raise ValidationError({"reserva": "No es la salida de un cliente sin reserva de este garaje."})
        if reserva.fin < inicio_de_caja(garaje):
            raise EstadoInvalido("Ese cobro ya entró en un cierre de caja: no se puede cambiar.")
        reserva.medio_cobro = medio
        reserva.save(update_fields=["medio_cobro"])
    return reserva


def cerrar(garaje_id, usuario, efectivo_contado, observaciones=""):
    if efectivo_contado < 0:
        raise ValidationError({"efectivo_contado": "No puede ser negativo."})
    with transaction.atomic():
        # Bloquea el garaje: dos cierres a la vez no pueden contar lo mismo
        garaje = Garaje.objects.select_for_update().get(pk=garaje_id)
        datos = resumen(garaje, inicio_de_caja(garaje), timezone.now())
        esperado = Decimal(datos["efectivo_esperado"])
        contado = Decimal(efectivo_contado).quantize(Decimal("0.01"))
        return CierreCaja.objects.create(
            garaje=garaje, cerrado_por=usuario, desde=datos["desde"], hasta=datos["hasta"],
            efectivo_esperado=esperado, efectivo_contado=contado, diferencia=contado - esperado,
            resumen={**datos, "desde": datos["desde"].isoformat(), "hasta": datos["hasta"].isoformat()},
            observaciones=observaciones.strip(),
        )
