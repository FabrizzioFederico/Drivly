from celery import shared_task

from .oauth import renovar_por_vencer


@shared_task(name="pagos.tasks.renovar_conexiones_mp")
def renovar_conexiones_mp():
    """Programada una vez por día en CELERY_BEAT_SCHEDULE (settings)."""
    return renovar_por_vencer()
