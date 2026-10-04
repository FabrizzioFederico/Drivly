import math
from decimal import Decimal

RADIO_TIERRA_M = 6_371_000


def distancia_m(lat1, lng1, lat2, lng2) -> float:
    """Distancia en metros entre dos puntos (fórmula de haversine)."""
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(a))


def caja_alrededor(lat, lng, radio_m):
    """Rectángulo que contiene el círculo: primer filtro barato en la base (usa el índice lat/lng)."""
    dlat = radio_m / 111_320
    dlng = radio_m / (111_320 * max(math.cos(math.radians(float(lat))), 0.01))
    lat, lng = float(lat), float(lng)
    return (Decimal(str(lat - dlat)), Decimal(str(lat + dlat)), Decimal(str(lng - dlng)), Decimal(str(lng + dlng)))
