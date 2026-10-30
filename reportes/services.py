"""Métricas del panel del admin (CU-10)."""
from datetime import datetime, time, timedelta

from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Sum
from django.utils import timezone

from operacion.models import Deuda, EstadoDeuda
from reservas.models import EstadoReserva, Modalidad, Reserva

# Las que usaron o tienen comprometido un lugar: FINALIZADA y CON_DEUDA ya no cuentan en la ocupación actual,
# pero sí en el pico de un día que ya pasó.
ESTADOS_USAN_LUGAR = (
    EstadoReserva.CONFIRMADA, EstadoReserva.EN_CURSO, EstadoReserva.FINALIZADA, EstadoReserva.CON_DEUDA,
)
ESTADOS_SIN_INGRESO = (EstadoReserva.CANCELADA, EstadoReserva.SIN_LUGAR)  # se reembolsan


def _pico(garaje, ini, fin, ahora):
    """(lugares, instante) de mayor ocupación. Basta con mirar `ini` y los inicios de reservas (regla 1)."""
    intervalos = []
    reservas = Reserva.objects.filter(
        garaje=garaje, estado__in=ESTADOS_USAN_LUGAR, periodo__overlap=DateTimeTZRange(ini, fin)
    ).only("periodo", "estado")
    for r in reservas:
        hasta = max(r.fin, ahora) if r.estado == EstadoReserva.EN_CURSO else r.fin  # overstay activo
        intervalos.append((r.inicio, hasta))
    instantes = {ini} | {i for i, _ in intervalos if ini < i < fin}
    return max(((sum(i <= t < h for i, h in intervalos), t) for t in instantes), key=lambda x: x[0])


def _suma(qs, campo):
    return float(qs.aggregate(total=Sum(campo))["total"] or 0)


def metricas_del_dia(garaje, fecha=None):
    ahora = timezone.now()
    fecha = fecha or timezone.localdate()
    ini = timezone.make_aware(datetime.combine(fecha, time.min))
    fin = ini + timedelta(days=1)
    reservas = Reserva.objects.filter(garaje=garaje)

    lugares, instante = _pico(garaje, ini, fin, ahora)
    confirmadas = reservas.filter(confirmada_en__gte=ini, confirmada_en__lt=fin)
    semana_pasada = reservas.filter(
        confirmada_en__gte=ini - timedelta(days=7), confirmada_en__lt=fin - timedelta(days=7)
    )
    app = _suma(confirmadas.exclude(estado__in=ESTADOS_SIN_INGRESO), "monto")
    presencial = _suma(
        reservas.filter(modalidad=Modalidad.PRESENCIAL, estado=EstadoReserva.FINALIZADA,
                        periodo__endswith__gte=ini, periodo__endswith__lt=fin),
        "monto",
    )
    excedentes = _suma(
        Deuda.objects.filter(reserva__garaje=garaje, estado=EstadoDeuda.PAGADA, pagada_en__gte=ini, pagada_en__lt=fin),
        "monto",
    )
    return {
        "ocupacion_pico": lugares / garaje.capacidad,
        "ocupacion_pico_lugares": lugares,
        "ocupacion_pico_hora": timezone.localtime(instante).strftime("%H:00"),
        "reservas_confirmadas": confirmadas.count(),
        "reservas_variacion": confirmadas.count() - semana_pasada.count(),
        "en_hold": reservas.filter(estado=EstadoReserva.HOLD, hold_expira__gt=ahora).count(),
        "canceladas": reservas.filter(estado=EstadoReserva.CANCELADA, creada_en__gte=ini, creada_en__lt=fin).count(),
        "recaudacion_total": app + presencial + excedentes,
        "recaudacion_app": app,
        "recaudacion_presencial": presencial,
        "recaudacion_excedentes": excedentes,
    }
