"""
Adaptador de patente.ar (diseño: integraciones · PatenteGateway).

El dominio sólo conoce `consultar_categoria(patente)`. Mientras no tengan el
contrato con patente.ar se usa MockPatenteGateway (PATENTE_AR_MOCK=True).
"""
import hashlib
import re
from dataclasses import dataclass, field

from django.conf import settings

from vehiculos.models import Categoria


class PatenteNoEncontrada(Exception):
    """El dominio no existe en el registro oficial."""


class ServicioPatenteNoDisponible(Exception):
    """Timeout, error de red o error del proveedor: hay que reintentar."""


@dataclass
class ResultadoPatente:
    categoria: str
    respuesta: dict = field(default_factory=dict)  # respuesta cruda, para ConsultaPatente


class MockPatenteGateway:
    """
    Simulación determinística para desarrollo y tests:
      - formatos de moto (123ABC, A123BCD)       -> MOTO
      - patentes terminadas en "ZZ" o "ZZZ"       -> no encontrada
      - patentes que empiezan con "ERR"          -> servicio no disponible
      - del resto, ~1 de cada 4 (por hash)        -> CAMIONETA, si no AUTO
    """

    def consultar_categoria(self, patente: str) -> ResultadoPatente:
        if patente.startswith("ERR"):
            raise ServicioPatenteNoDisponible("Mock: servicio caído")
        if patente.endswith("ZZ"):
            raise PatenteNoEncontrada(patente)
        if re.match(r"^(\d{3}[A-Z]{3}|[A-Z]\d{3}[A-Z]{3})$", patente):
            categoria = Categoria.MOTO
        elif int(hashlib.sha256(patente.encode()).hexdigest(), 16) % 4 == 0:
            categoria = Categoria.CAMIONETA
        else:
            categoria = Categoria.AUTO
        return ResultadoPatente(categoria=categoria, respuesta={"mock": True, "categoria": categoria})


class PatenteArGateway:
    """
    Integración real. Completar cuando tengan la documentación y credenciales de
    patente.ar: endpoint, autenticación (PATENTE_AR_API_KEY), formato de respuesta y
    cómo mapea su tipo de vehículo a AUTO / MOTO / CAMIONETA. Usar timeout corto y
    traducir errores de red a ServicioPatenteNoDisponible.
    """

    def consultar_categoria(self, patente: str) -> ResultadoPatente:
        raise ServicioPatenteNoDisponible("Integración con patente.ar pendiente de implementar")


def get_patente_gateway():
    return MockPatenteGateway() if settings.PATENTE_AR_MOCK else PatenteArGateway()
