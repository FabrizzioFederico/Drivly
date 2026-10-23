import calendar
from datetime import timedelta

from .models import Modalidad


def sumar_meses(fecha, meses: int):
    """31/01 + 1 mes = 28/02 (o 29): se ajusta al último día del mes destino."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


def fin_de_abono(inicio, modalidad):
    if modalidad == Modalidad.SEMANAL:
        return inicio + timedelta(days=7)
    if modalidad == Modalidad.MENSUAL:
        return sumar_meses(inicio, 1)
    if modalidad == Modalidad.ANUAL:
        return sumar_meses(inicio, 12)
    raise ValueError(f"{modalidad} no es un abono")
