from celery import shared_task

from . import services

# Un SMTP o FCM caído no pierde el comprobante: se reintenta con espera creciente (hasta ~1 h)
REINTENTOS = {"autoretry_for": (Exception,), "retry_backoff": 60, "retry_backoff_max": 3600, "max_retries": 6}


@shared_task(name="notificaciones.tasks.reserva_confirmada", **REINTENTOS)
def reserva_confirmada(reserva_id):
    services.reserva_confirmada(reserva_id)


@shared_task(name="notificaciones.tasks.deuda_pagada", **REINTENTOS)
def deuda_pagada(reserva_id):
    services.deuda_pagada(reserva_id)


@shared_task(name="notificaciones.tasks.reembolso", **REINTENTOS)
def reembolso(pago_id):
    services.reembolso(pago_id)


@shared_task(name="notificaciones.tasks.recordar_inicios")
def recordar_inicios():
    return services.recordar_inicios()


@shared_task(name="notificaciones.tasks.avisar_fines")
def avisar_fines():
    return services.avisar_fines()


@shared_task(name="notificaciones.tasks.pedir_calificaciones")
def pedir_calificaciones():
    return services.pedir_calificaciones()
