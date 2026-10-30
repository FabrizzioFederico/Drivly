from celery import shared_task

from .services import marcar_incobrables, recordar_deudas as _recordar_deudas


@shared_task(name="operacion.tasks.recordar_deudas")
def recordar_deudas():
    """Programada cada 15 minutos en CELERY_BEAT_SCHEDULE (settings)."""
    return _recordar_deudas()


@shared_task(name="operacion.tasks.marcar_deudas_incobrables")
def marcar_deudas_incobrables():
    """Programada una vez por día en CELERY_BEAT_SCHEDULE (settings)."""
    return marcar_incobrables()
