"""
Foto ilustrativa del vehículo (marca, modelo y año de DataCar) desde carapi.trustcar.info.

El servicio no está documentado: responde con una redirección a una foto de Wikimedia Commons y manda el autor
en `x-image-attribution`. Las licencias de Commons (CC BY, CC BY-SA) obligan a mostrar ese crédito junto a la foto.
Si no conoce el vehículo redirige a una imagen genérica: eso cuenta como "sin foto".
Cualquier falla devuelve None: la foto es decorativa y nunca frena el alta de un vehículo.
"""
import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

URL = "https://carapi.trustcar.info/getImage"
TIMEOUT_S = 3


@dataclass
class Foto:
    url: str
    credito: str


def _texto_de_encabezado(valor: str) -> str:
    """
    El servicio manda el crédito en UTF-8 ("—", "©"), pero los encabezados HTTP se leen como Latin-1:
    sin esto se guardaba "Peugeot 504 â€” Â© ...". Si no era UTF-8, queda como vino.
    """
    try:
        return valor.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return valor


def _modelos_a_probar(modelo: str) -> list[str]:
    """DataCar manda la versión completa ("KANGOO II EXPRESS EMOTION"); el servicio conoce el modelo base ("KANGOO")."""
    modelo = " ".join(modelo.split())
    if not modelo:
        return []
    base = modelo.split(" ")[0]
    # "504XSDTCADA": a veces la versión viene pegada al número del modelo
    numero = re.match(r"^\d{3,4}(?=[A-Z])", base.upper())
    candidatos = [modelo, base, numero.group(0) if numero else ""]
    return list(dict.fromkeys(c for c in candidatos if c))  # sin repetidos, en orden


def buscar(marca: str, modelo: str, anio: int | None) -> Foto | None:
    if not marca or not modelo:
        return None
    for candidato in _modelos_a_probar(modelo):
        parametros = {"make": marca.title(), "model": candidato.title()}
        if anio:
            parametros["year"] = anio
        try:
            r = requests.get(URL, params=parametros, allow_redirects=False, timeout=TIMEOUT_S)
        except requests.RequestException as error:
            logger.info("No se pudo buscar la foto de %s %s: %s", marca, candidato, type(error).__name__)
            return None
        destino = r.headers.get("location", "")
        if r.status_code in (301, 302, 303, 307, 308) and destino.startswith("https://") and "placeholder" not in destino:
            credito = _texto_de_encabezado(r.headers.get("x-image-attribution", ""))
            return Foto(url=destino[:500], credito=credito[:200])
    return None
