from django.db import transaction
from django.utils import timezone

from integraciones.patente import (
    PatenteNoEncontrada,
    ServicioPatenteNoDisponible,
    get_patente_gateway,
)

from .models import ConsultaPatente, EstadoValidacion, Vehiculo


@transaction.atomic
def validar_vehiculo(vehiculo: Vehiculo, gateway=None) -> Vehiculo:
    """
    Consulta patente.ar y fija la categoría (regla 3). Nunca lanza por errores del
    proveedor: si el servicio no responde, el vehículo queda PENDIENTE para reintentar
    (más adelante, con una tarea de Celery).
    """
    gateway = gateway or get_patente_gateway()
    try:
        resultado = gateway.consultar_categoria(vehiculo.patente)
    except PatenteNoEncontrada:
        ConsultaPatente.objects.create(vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.NO_ENCONTRADA)
        vehiculo.estado_validacion = EstadoValidacion.RECHAZADO
        vehiculo.categoria = None
        vehiculo.validado_en = None
    except ServicioPatenteNoDisponible as error:
        ConsultaPatente.objects.create(
            vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.ERROR, respuesta={"error": str(error)}
        )
        vehiculo.estado_validacion = EstadoValidacion.PENDIENTE
    else:
        ConsultaPatente.objects.create(
            vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.OK, respuesta=resultado.respuesta
        )
        vehiculo.categoria = resultado.categoria
        vehiculo.estado_validacion = EstadoValidacion.VALIDADO
        vehiculo.validado_en = timezone.now()
    vehiculo.save(update_fields=["categoria", "estado_validacion", "validado_en"])
    return vehiculo
