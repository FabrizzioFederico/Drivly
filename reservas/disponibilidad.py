"""Búsqueda de garajes con lugar (regla 6: si un garaje está lleno, se ofrecen los cercanos)."""
from decimal import Decimal

from django.conf import settings
from django.db.models import Min

from garajes.geo import caja_alrededor, distancia_m
from garajes.models import Garaje, Tarifa

from .models import Modalidad
from .ocupacion import lugares_libres

UNIDAD = {Modalidad.HORA: "/ 15 min", Modalidad.SEMANAL: "/ semana", Modalidad.MENSUAL: "/ mes", Modalidad.ANUAL: "/ año"}


def garajes_con_disponibilidad(lat, lng, ini, fin, modalidad=Modalidad.HORA, radio=None, excluir_id=None, solo_con_lugar=False):
    """
    Garajes activos que ofrecen la modalidad, dentro del radio, ordenados por distancia,
    con `lugares_libres` en todo el intervalo y el precio más bajo de esa modalidad.
    """
    radio = radio or settings.DRIVLY_RADIO_CERCANOS_M
    lat, lng = Decimal(str(lat)), Decimal(str(lng))
    lat_min, lat_max, lng_min, lng_max = caja_alrededor(lat, lng, radio)
    campo_precio = "precio_fraccion" if modalidad == Modalidad.HORA else "precio_periodo"
    precios = dict(
        Tarifa.objects.filter(modalidad=modalidad).values_list("garaje_id").annotate(p=Min(campo_precio))
    )
    candidatos = Garaje.objects.filter(
        activo=True, id__in=precios.keys(), lat__range=(lat_min, lat_max), lng__range=(lng_min, lng_max)
    )
    if excluir_id:
        candidatos = candidatos.exclude(id=excluir_id)

    resultado = []
    for g in candidatos:
        distancia = distancia_m(lat, lng, g.lat, g.lng)
        if distancia > radio:
            continue
        libres = lugares_libres(g, ini, fin, modalidad)
        if solo_con_lugar and libres <= 0:
            continue
        resultado.append({
            "id": g.id, "nombre": g.nombre, "direccion": g.direccion, "lat": g.lat, "lng": g.lng,
            "distancia_m": round(distancia), "lugares_libres": libres,
            "precio_desde": precios[g.id], "precio_unidad": UNIDAD[modalidad],
        })
    return sorted(resultado, key=lambda x: x["distancia_m"])


def cercanos_a(garaje, ini, fin, modalidad=Modalidad.HORA):
    return garajes_con_disponibilidad(
        garaje.lat, garaje.lng, ini, fin, modalidad, excluir_id=garaje.id, solo_con_lugar=True
    )
