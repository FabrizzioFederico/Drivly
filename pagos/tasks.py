from celery import shared_task

from .oauth import renovar_por_vencer
from .services import conciliar_pagos as _conciliar_pagos
from .services import reintentar_reembolsos as _reintentar_reembolsos


@shared_task(name="pagos.tasks.renovar_conexiones_mp")
def renovar_conexiones_mp():
    """Programada una vez por día en CELERY_BEAT_SCHEDULE (settings)."""
    return renovar_por_vencer()


@shared_task(name="pagos.tasks.reintentar_reembolsos")
def reintentar_reembolsos():
    """Programada cada 15 minutos en CELERY_BEAT_SCHEDULE (settings)."""
    return _reintentar_reembolsos()


@shared_task(name="pagos.tasks.conciliar_pagos")
def conciliar_pagos():
    """Programada cada 10 minutos en CELERY_BEAT_SCHEDULE (settings): recupera pagos cuyo webhook no llegó."""
    return _conciliar_pagos()
