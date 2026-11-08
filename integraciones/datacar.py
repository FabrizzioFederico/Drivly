"""
Adaptador de DataCar API (regla 3: la categoría del vehículo sale de una fuente externa).

El dominio sólo conoce `consultar(patente) -> ResultadoPatente`. En desarrollo y en los tests
se usa SimuladorDataCar (DATACAR_MOCK=True); en producción, DataCarGateway.
"""
import hashlib
import logging
import unicodedata
from dataclasses import dataclass, field

import requests
from django.conf import settings

from vehiculos.models import Categoria


class PatenteNoEncontrada(Exception):
    """El dominio no figura en la fuente."""


class ServicioPatenteNoDisponible(Exception):
    """Timeout, error de red o del proveedor: se puede reintentar."""


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower().replace("-", "").replace(" ", "")


logger = logging.getLogger(__name__)

# Traducción de la clasificación de DataCar a las categorías de Drivly (documentación, regla 3).
# DataCar devuelve el tipo del registro automotor en mayúsculas y a veces con agregados
# ("SEDAN 4 PUERTAS", "PICK-UP CABINA DOBLE"): se busca la palabra clave dentro del texto.
CLASIFICACION_A_CATEGORIA = {
    "sedan": Categoria.AUTO, "hatchback": Categoria.AUTO, "coupe": Categoria.AUTO,
    "rural": Categoria.AUTO, "familiar": Categoria.AUTO, "convertible": Categoria.AUTO, "berlina": Categoria.AUTO,
    "suv": Categoria.CAMIONETA, "pickup": Categoria.CAMIONETA, "furgon": Categoria.CAMIONETA,
    "utilitario": Categoria.CAMIONETA, "minivan": Categoria.CAMIONETA, "todoterreno": Categoria.CAMIONETA,
    "jeep": Categoria.CAMIONETA,
    "moto": Categoria.MOTO, "motocicleta": Categoria.MOTO, "ciclomotor": Categoria.MOTO,
    "cuatriciclo": Categoria.MOTO,
}


# Primero las claves largas, para que "furgoneta" no dependa del orden del diccionario.
_CLAVES_POR_LARGO = sorted(CLASIFICACION_A_CATEGORIA, key=len, reverse=True)


def categoria_desde_clasificacion(clasificacion: str):
    """Devuelve la categoría o None si la clasificación no tiene traducción (pasa a declaración)."""
    texto = _normalizar(clasificacion)
    if not texto:
        return None
    if texto in CLASIFICACION_A_CATEGORIA:
        return CLASIFICACION_A_CATEGORIA[texto]
    return next((CLASIFICACION_A_CATEGORIA[c] for c in _CLAVES_POR_LARGO if c in texto), None)


@dataclass
class ResultadoPatente:
    clasificacion: str
    respuesta: dict = field(default_factory=dict)  # respuesta cruda, para ConsultaPatente

    marca: str = ""
    modelo: str = ""
    anio: int | None = None

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
        return ResultadoPatente(clasificacion, {"simulado": True, "clasificacion": clasificacion},
                                marca="SIMULADA", modelo=f"Modelo de prueba ({clasificacion})", anio=2020)


class DataCarGateway:
    """
    Integración real: GET {DATACAR_API_URL}vehicle/{patente}. Contrato tomado de la demo oficial
    (demo.datacarapi.com):
      - Autenticación: header Authorization "bearer <key>" si la key empieza con "dca"; si no, "basic <key>".
      - Éxito: {"success": true, "data": {"id": {"brand", "model", "year", "type", ...}}, "balance": n}
      - Error: status distinto de 2xx con {"error": {"code", "message"}}.
    Cualquier falla termina en declaración del conductor: nunca bloquea el alta.
    """

    URL_POR_DEFECTO = "https://api.datacar.com.ar/"
    TIMEOUT_S = 3

    def consultar(self, patente: str) -> ResultadoPatente:
        clave = settings.DATACAR_API_KEY
        if not clave:
            raise ServicioPatenteNoDisponible("Falta DATACAR_API_KEY")
        base = (settings.DATACAR_API_URL or self.URL_POR_DEFECTO).rstrip("/") + "/"
        esquema = "bearer" if clave.startswith("dca") else "basic"
        try:
            r = requests.get(
                f"{base}vehicle/{patente.lower()}",
                headers={"Authorization": f"{esquema} {clave}", "Accept": "application/json"},
                timeout=self.TIMEOUT_S,
            )
        except requests.RequestException as error:
            raise ServicioPatenteNoDisponible(f"DataCar no respondió: {type(error).__name__}") from error
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}
        if not isinstance(cuerpo, dict):
            cuerpo = {}

        if r.status_code == 404:
            raise PatenteNoEncontrada(patente)
        if not r.ok:
            detalle = (cuerpo.get("error") or {}).get("message") or r.reason
            if r.status_code in (401, 402, 403):  # key inválida o sin saldo: hay que actuar
                logger.error("DataCar rechazó la consulta (%s): %s", r.status_code, detalle)
            raise ServicioPatenteNoDisponible(f"DataCar {r.status_code}: {detalle}")

        vehiculo = (cuerpo.get("data") or {}).get("id") or {}
        if not cuerpo.get("success") or not vehiculo.get("type"):
            raise PatenteNoEncontrada(patente)
        logger.info("DataCar consultada: saldo restante %s", cuerpo.get("balance"))
        anio = vehiculo.get("year")
        return ResultadoPatente(
            str(vehiculo["type"]),
            cuerpo,
            marca=str(vehiculo.get("brand") or "")[:60],
            modelo=str(vehiculo.get("model") or "")[:120],
            anio=anio if isinstance(anio, int) and 1900 <= anio <= 2100 else None,
        )


def get_patente_gateway():
    return SimuladorDataCar() if settings.DATACAR_MOCK else DataCarGateway()
