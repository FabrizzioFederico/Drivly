"""
Ocupación pico (documentación, regla 1).

La ocupación sólo sube cuando empieza una reserva, así que el máximo dentro de [ini, fin)
se alcanza en `ini` o en el inicio de alguna reserva solapada: alcanza con evaluar esos puntos.
Contar reservas solapadas NO sirve: 13-14 y 15-16 se solapan con 13-16 pero nunca coexisten.
"""
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q
from django.utils import timezone

from .models import ESTADOS_OCUPAN, MODALIDADES_ABONO, EstadoReserva, Modalidad, Reserva


@dataclass(frozen=True)
class Ocupante:
    inicio: datetime
    fin: datetime  # fin efectivo (proyectado si hay overstay activo)
    modalidad: str
    estado: str


def ocupantes(garaje_id, ini, fin, ahora=None, excluir_id=None) -> list[Ocupante]:
    """
    Reservas que ocupan lugar en algún momento de [ini, fin):
      - HOLD vigente, CONFIRMADA y EN_CURSO (abonos y presenciales incluidos).
      - Un EN_CURSO cuyo fin ya pasó (overstay activo) se proyecta ocupando hasta
        ahora + DRIVLY_OVERSTAY_PROYECCION: el auto sigue adentro.
    """
    ahora = ahora or timezone.now()
    proyeccion = ahora + settings.DRIVLY_OVERSTAY_PROYECCION
    qs = (
        Reserva.objects.filter(garaje_id=garaje_id, estado__in=ESTADOS_OCUPAN)
        .filter(
            Q(periodo__overlap=DateTimeTZRange(ini, fin))
            | Q(estado=EstadoReserva.EN_CURSO, periodo__endswith__lt=ahora)
        )
        .exclude(estado=EstadoReserva.HOLD, hold_expira__lte=ahora)  # liberación lógica del hold (regla 2)
        .only("periodo", "modalidad", "estado")
    )
    if excluir_id:
        qs = qs.exclude(id=excluir_id)
    resultado = []
    for r in qs:
        fin_efectivo = r.fin
        if r.estado == EstadoReserva.EN_CURSO and fin_efectivo < ahora:
            fin_efectivo = max(fin_efectivo, proyeccion)
        if r.inicio < fin and fin_efectivo > ini:
            resultado.append(Ocupante(r.inicio, fin_efectivo, r.modalidad, r.estado))
    return resultado


def pico(lista: list[Ocupante], ini, fin) -> int:
    puntos = {ini} | {o.inicio for o in lista if ini < o.inicio < fin}
    return max((sum(1 for o in lista if o.inicio <= t < o.fin) for t in puntos), default=0)


def ocupacion_pico(garaje_id, ini, fin, ahora=None, excluir_id=None) -> int:
    return pico(ocupantes(garaje_id, ini, fin, ahora, excluir_id), ini, fin)


def lugares_libres(garaje, ini, fin, modalidad=Modalidad.HORA, ahora=None, excluir_id=None) -> int:
    """
    Lugares disponibles en TODO el intervalo. Para abonos además se respeta el cupo de abonos,
    para que no se coman la rotación por hora (regla 5).
    """
    lista = ocupantes(garaje.id, ini, fin, ahora, excluir_id)
    libres = garaje.capacidad - pico(lista, ini, fin)
    if modalidad in MODALIDADES_ABONO:
        abonos = [o for o in lista if o.modalidad in MODALIDADES_ABONO]
        libres = min(libres, garaje.cupo_abonos - pico(abonos, ini, fin))
    return max(0, libres)
