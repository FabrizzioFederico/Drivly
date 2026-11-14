"""Reseñas de los garajes: sólo opina quien estacionó, una vez por reserva y hasta 30 días después."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from reservas.exceptions import EstadoInvalido
from reservas.models import EstadoReserva

from .models import Resena

# Una estadía terminada: la reserva por la app que pasó por el garaje (con o sin exceso pagado)
ESTADOS_CALIFICABLES = (EstadoReserva.FINALIZADA, EstadoReserva.CON_DEUDA)
PLAZO_PARA_CALIFICAR = timedelta(days=30)


def se_puede_calificar(reserva) -> bool:
    return (
        reserva.conductor_id is not None
        and reserva.estado in ESTADOS_CALIFICABLES
        and timezone.now() <= reserva.fin + PLAZO_PARA_CALIFICAR
    )


@transaction.atomic
def calificar(reserva, estrellas, comentario=""):
    """Crea la reseña o la corrige (mismo plazo). Corregirla borra la respuesta del garaje, que era a otro texto."""
    if not se_puede_calificar(reserva):
        raise EstadoInvalido("Podés calificar el garaje cuando termina tu estadía, hasta 30 días después.")
    resena, creada = Resena.objects.select_for_update().get_or_create(
        reserva=reserva,
        defaults={"garaje_id": reserva.garaje_id, "conductor_id": reserva.conductor_id,
                  "estrellas": estrellas, "comentario": comentario.strip()},
    )
    if not creada and (resena.estrellas, resena.comentario) != (estrellas, comentario.strip()):
        resena.estrellas, resena.comentario = estrellas, comentario.strip()
        resena.respuesta, resena.respondida_en = "", None
        resena.save()
    return resena


def responder(resena, texto):
    resena.respuesta = texto.strip()
    resena.respondida_en = timezone.now() if resena.respuesta else None
    resena.save(update_fields=["respuesta", "respondida_en", "actualizada_en"])
    return resena
