"""
Notificaciones push con Firebase Cloud Messaging (API HTTP v1).
Sin FCM_PROJECT_ID y FCM_CREDENCIALES (JSON de una cuenta de servicio del proyecto de Firebase) queda desactivado:
los avisos se siguen registrando y los emails salen igual.
"""
import logging

import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

ALCANCE = "https://www.googleapis.com/auth/firebase.messaging"
_credenciales = None


def habilitado() -> bool:
    return bool(settings.FCM_PROJECT_ID and settings.FCM_CREDENCIALES)


def _token_de_acceso() -> str:
    """Token OAuth de la cuenta de servicio; dura una hora y se renueva solo."""
    global _credenciales
    if _credenciales is None:
        _credenciales = service_account.Credentials.from_service_account_file(settings.FCM_CREDENCIALES, scopes=[ALCANCE])
    if not _credenciales.valid:
        _credenciales.refresh(Request())
    return _credenciales.token


def _token_invalido(respuesta) -> bool:
    """La app se desinstaló o el token venció: hay que olvidarlo."""
    if respuesta.status_code == 404:
        return True
    try:
        detalles = respuesta.json()["error"].get("details", [])
    except (ValueError, KeyError, AttributeError):
        return False
    return any(d.get("errorCode") in ("UNREGISTERED", "INVALID_ARGUMENT") for d in detalles)


def enviar(usuario, titulo: str, cuerpo: str, datos: dict | None = None, canal_android: str = "reservas") -> int:
    """Manda la notificación a todos los teléfonos del usuario. Devuelve a cuántos llegó."""
    if not habilitado():
        logger.info("Push desactivado (sin FCM_PROJECT_ID/FCM_CREDENCIALES): %s", titulo)
        return 0
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
    enviados = 0
    for dispositivo in list(usuario.dispositivos.all()):
        mensaje = {
            "token": dispositivo.token,
            "notification": {"title": titulo, "body": cuerpo},
            # FCM sólo acepta textos en `data`
            "data": {k: str(v) for k, v in (datos or {}).items()},
            "android": {"priority": "high", "notification": {"channel_id": canal_android}},
        }
        respuesta = requests.post(
            url, json={"message": mensaje}, headers={"Authorization": f"Bearer {_token_de_acceso()}"}, timeout=5
        )
        if respuesta.ok:
            enviados += 1
        elif _token_invalido(respuesta):
            dispositivo.delete()
        else:
            # Un error de FCM no corta los demás teléfonos; la tarea lo reintenta si no llegó a ninguno
            logger.warning("FCM respondió %s para %s: %s", respuesta.status_code, usuario, respuesta.text[:300])
    return enviados
