"""
Validación de categoría en capas (documentación, regla 3):
  1. Formato de patente de moto  -> MOTO sin consultar nada.
  2. DataCar API                 -> clasificación traducida a AUTO / CAMIONETA / MOTO.
  3. Declaración del conductor   -> respaldo si DataCar no responde, no tiene el dominio
                                    o devuelve una clasificación sin traducción.
  4. Verificación del playero    -> en el primer ingreso confirma o corrige.
Ninguna capa bloquea por una API externa: si DataCar falla, el conductor declara.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from integraciones.datacar import (
    PatenteNoEncontrada,
    ServicioPatenteNoDisponible,
    get_patente_gateway,
)

from .models import (
    Categoria,
    ConsultaPatente,
    EstadoValidacion,
    OrigenCategoria,
    Vehiculo,
)

CATEGORIAS_DECLARABLES = {Categoria.AUTO, Categoria.CAMIONETA}


def _asignar(vehiculo: Vehiculo, categoria, origen):
    vehiculo.categoria = categoria
    vehiculo.categoria_origen = origen
    vehiculo.estado_validacion = EstadoValidacion.VALIDADO
    vehiculo.validado_en = timezone.now()


@transaction.atomic
def validar_vehiculo(vehiculo: Vehiculo, gateway=None) -> Vehiculo:
    """Capas 1 y 2. Nunca lanza por errores del proveedor: deja el vehículo listo para declarar."""
    if vehiculo.es_moto:
        _asignar(vehiculo, Categoria.MOTO, OrigenCategoria.FORMATO)
    elif vehiculo.categoria_origen != OrigenCategoria.VERIFICADA:  # lo verificado en persona no se pisa
        gateway = gateway or get_patente_gateway()
        try:
            resultado = gateway.consultar(vehiculo.patente)
        except PatenteNoEncontrada:
            ConsultaPatente.objects.create(vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.NO_ENCONTRADA)
        except ServicioPatenteNoDisponible as error:
            ConsultaPatente.objects.create(
                vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.ERROR, respuesta={"error": str(error)}
            )
        else:
            ConsultaPatente.objects.create(
                vehiculo=vehiculo, resultado=ConsultaPatente.Resultado.OK, respuesta=resultado.respuesta
            )
            if resultado.categoria:  # DataCar prevalece sobre una declaración
                _asignar(vehiculo, resultado.categoria, OrigenCategoria.DATACAR)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en"])
    return vehiculo


def puede_declarar(vehiculo: Vehiculo) -> bool:
    return (
        not vehiculo.es_moto
        and vehiculo.categoria_origen in (None, OrigenCategoria.DECLARADA)
        and vehiculo.conductor.puede_declarar_categoria
    )


@transaction.atomic
def declarar_categoria(vehiculo: Vehiculo, categoria: str) -> Vehiculo:
    """Capa 3: el conductor declara auto o camioneta cuando no hay dato de DataCar."""
    if categoria not in CATEGORIAS_DECLARABLES:
        raise ValidationError({"categoria": "Sólo se puede declarar AUTO o CAMIONETA."})
    if not vehiculo.conductor.puede_declarar_categoria:
        raise PermissionDenied("Tu cuenta tuvo correcciones de categoría: la verifica un playero en tu próximo ingreso.")
    if not puede_declarar(vehiculo):
        raise ValidationError({"categoria": "La categoría de este vehículo ya está definida y no se puede declarar."})
    _asignar(vehiculo, categoria, OrigenCategoria.DECLARADA)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en"])
    return vehiculo


@transaction.atomic
def verificar_por_playero(vehiculo: Vehiculo, categoria_real: str) -> bool:
    """
    Capa 4, en el ingreso. Devuelve True si hubo corrección. El cobro de la diferencia y el
    incidente se resuelven en la app `operacion` (Sprint 4), que llama a esta función.
    """
    corrigio = vehiculo.categoria != categoria_real
    if corrigio and vehiculo.categoria_origen == OrigenCategoria.DECLARADA:
        conductor = vehiculo.conductor
        conductor.correcciones_categoria += 1
        conductor.save(update_fields=["correcciones_categoria"])
    _asignar(vehiculo, categoria_real, OrigenCategoria.VERIFICADA)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en"])
    return corrigio
