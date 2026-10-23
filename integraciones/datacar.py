"""
Adaptador de DataCar API (regla 3: la categoría del vehículo sale de una fuente externa).

El dominio sólo conoce `consultar(patente) -> ResultadoPatente`. Mientras no tengan
credenciales y un ejemplo de respuesta, se usa SimuladorDataCar (DATACAR_MOCK=True).
"""
import hashlib
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings

from vehiculos.models import Categoria


class PatenteNoEncontrada(Exception):
    """El dominio no figura en la fuente."""


class ServicioPatenteNoDisponible(Exception):
    """Timeout, error de red o del proveedor: se puede reintentar."""


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower().replace("-", "").replace(" ", "")


# Traducción de la clasificación de DataCar a las categorías de Drivly (documentación, regla 3).
# Se completa cuando DataCar entregue la lista real de clasificaciones.
CLASIFICACION_A_CATEGORIA = {
    "sedan": Categoria.AUTO, "hatchback": Categoria.AUTO, "coupe": Categoria.AUTO,
    "rural": Categoria.AUTO, "familiar": Categoria.AUTO, "convertible": Categoria.AUTO,
    "suv": Categoria.CAMIONETA, "pickup": Categoria.CAMIONETA, "furgon": Categoria.CAMIONETA,
    "utilitario": Categoria.CAMIONETA, "minivan": Categoria.CAMIONETA, "todoterreno": Categoria.CAMIONETA,
    "moto": Categoria.MOTO, "motocicleta": Categoria.MOTO, "ciclomotor": Categoria.MOTO,
    "cuatriciclo": Categoria.MOTO,
}


def categoria_desde_clasificacion(clasificacion: str):
    """Devuelve la categoría o None si la clasificación no tiene traducción (pasa a declaración)."""
    return CLASIFICACION_A_CATEGORIA.get(_normalizar(clasificacion))


@dataclass
class ResultadoPatente:
    clasificacion: str
    respuesta: dict = field(default_factory=dict)  # respuesta cruda, para ConsultaPatente

    @property
    def categoria(self):
        return categoria_desde_clasificacion(self.clasificacion)


class SimuladorDataCar:
    """
    Respuestas predecibles para desarrollo y tests:
      - empieza con "ERR"  -> servicio caído
      - termina en "ZZ"    -> dominio no encontrado
      - empieza con "XX"   -> clasificación sin traducción ("Casa rodante")
      - empieza con "AE"   -> SUV · "AF" -> Pick-up
      - el resto           -> Sedán o Hatchback
    """

    def consultar(self, patente: str) -> ResultadoPatente:
        if patente.startswith("ERR"):
            raise ServicioPatenteNoDisponible("Simulador: servicio caído")
        if patente.endswith("ZZ"):
            raise PatenteNoEncontrada(patente)
        if patente.startswith("XX"):
            clasificacion = "Casa rodante"
        elif patente.startswith("AE"):
            clasificacion = "SUV"
        elif patente.startswith("AF"):
            clasificacion = "Pick-up"
        else:
            clasificacion = "Sedán" if int(hashlib.sha256(patente.encode()).hexdigest(), 16) % 2 else "Hatchback"
        return ResultadoPatente(clasificacion, {"simulado": True, "clasificacion": clasificacion})


class DataCarGateway:
    """
    Integración real. Completar con la documentación de DataCar: URL, autenticación
    (DATACAR_API_KEY), nombre del campo de clasificación y códigos de error.
    Usar timeout corto (3 s) y traducir errores de red a ServicioPatenteNoDisponible.
    """

    TIMEOUT_S = 3

    def consultar(self, patente: str) -> ResultadoPatente:
        raise ServicioPatenteNoDisponible("Integración con DataCar pendiente de implementar")


def get_patente_gateway():
    return SimuladorDataCar() if settings.DATACAR_MOCK else DataCarGateway()
