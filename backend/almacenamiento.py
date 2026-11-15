"""
Fotos subidas (perfil y garajes) en Cloudinary.

En Render el disco se borra en cada deploy: las fotos tienen que vivir afuera. Se activa sola cuando existe la variable
CLOUDINARY_URL (cloudinary://API_KEY:API_SECRET@CLOUD_NAME, el SDK la lee del entorno); sin ella quedan en la carpeta
media/ como en desarrollo.

Los nombres ya son únicos (un uuid por subida, ver cuentas.models.ruta_foto y garajes.models.ruta_foto_garaje): no hace
falta preguntarle a Cloudinary si existen, y la URL de cada foto nunca muestra una versión vieja desde la caché.
"""
import logging
import posixpath

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

CARPETA = "drivly"  # todo queda bajo esta carpeta en la Media Library de Cloudinary


class FotoNoDisponible(APIException):
    """Cloudinary rechazó la subida (credenciales mal cargadas) o no respondió: la app muestra este mensaje."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "No se pudo guardar la foto en este momento. Probá de nuevo en unos minutos."
    default_code = "FOTO_NO_DISPONIBLE"


@deconstructible
class CloudinaryStorage(Storage):
    @staticmethod
    def _public_id(nombre):
        """fotos/<usuario>/<uuid>.jpg -> drivly/fotos/<usuario>/<uuid> (Cloudinary guarda el formato aparte)."""
        return posixpath.join(CARPETA, posixpath.splitext(nombre)[0])

    @staticmethod
    def _formato(nombre):
        return posixpath.splitext(nombre)[1].lstrip(".") or "jpg"

    def _save(self, nombre, contenido):
        contenido.seek(0)
        try:
            cloudinary.uploader.upload(
                contenido, public_id=self._public_id(nombre), resource_type="image", overwrite=True, invalidate=True,
            )
        except Exception as error:  # 401 con credenciales mal cargadas (p. ej. "cloud_name mismatch"), red caída
            logger.exception("Cloudinary no guardó %s: %s", nombre, error)
            raise FotoNoDisponible()
        return nombre

    def url(self, nombre):
        url, _ = cloudinary.utils.cloudinary_url(self._public_id(nombre), secure=True, format=self._formato(nombre))
        return url

    def delete(self, nombre):
        if not nombre:
            return
        try:
            cloudinary.uploader.destroy(self._public_id(nombre), resource_type="image", invalidate=True)
        except Exception:  # la foto nueva ya quedó guardada: una vieja sin borrar no frena nada
            logger.exception("Cloudinary no borró %s", nombre)

    def exists(self, nombre):
        return False  # nombres únicos: nunca se pisa una foto existente
