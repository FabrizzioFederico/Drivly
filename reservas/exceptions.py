from rest_framework import status
from rest_framework.exceptions import APIException


class ReservaError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "RESERVA_ERROR"

    def __init__(self, detail=None, **extra):
        super().__init__(detail)
        self.extra = extra  # datos para el frontend, ej. garajes cercanos


class SinCupo(ReservaError):
    default_detail = "No queda lugar en este garaje para todo ese horario."
    default_code = "SIN_CUPO"


class SinCupoAbonos(SinCupo):
    default_detail = "Este garaje ya no tiene lugares disponibles para abonos en ese período."


class SinTarifa(ReservaError):
    default_detail = "Este garaje no ofrece esa modalidad para tu vehículo."
    default_code = "SIN_TARIFA"


class VehiculoSinCategoria(ReservaError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Tu vehículo todavía no tiene categoría: declarala para poder reservar."
    default_code = "VEHICULO_SIN_CATEGORIA"


class VehiculoOcupado(ReservaError):
    default_detail = "Este vehículo ya tiene una reserva que se superpone con ese horario."
    default_code = "VEHICULO_OCUPADO"


class DeudaPendiente(ReservaError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Tenés una deuda pendiente: saldala para poder reservar."
    default_code = "DEUDA_PENDIENTE"


class EstadoInvalido(ReservaError):
    default_code = "ESTADO_INVALIDO"


class GarajeSinMercadoPago(ReservaError):
    default_detail = "Este garaje todavía no puede cobrar con Mercado Pago. Probá con otro garaje."
    default_code = "GARAJE_SIN_MERCADO_PAGO"


class HoldVencidoSinCupo(ReservaError):
    default_detail = "Pasaron los 5 minutos y el lugar ya fue tomado. Se reintegra el pago."
    default_code = "HOLD_VENCIDO_SIN_CUPO"


def manejador_errores(exc, context):
    """Agrega `code` y los datos extra (p. ej. `cercanos`) a la respuesta de error de DRF."""
    from rest_framework.views import exception_handler

    respuesta = exception_handler(exc, context)
    if respuesta is not None and isinstance(exc, ReservaError):
        respuesta.data = {"detail": str(exc.detail), "code": exc.default_code, **exc.extra}
    return respuesta
