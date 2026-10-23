from celery import shared_task

from .services import expirar_holds as _expirar_holds


@shared_task(name="reservas.tasks.expirar_holds")
def expirar_holds():
    """Programada cada minuto en CELERY_BEAT_SCHEDULE (settings)."""
    return _expirar_holds()
