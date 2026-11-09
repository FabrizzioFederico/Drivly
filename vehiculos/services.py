"""
Validación de categoría en capas (documentación, regla 3):
  1. Formato de patente de moto  -> MOTO sin consultar nada.
  2. DataCar API                 -> clasificación traducida a AUTO / CAMIONETA / MOTO.
  3. Declaración del conductor   -> respaldo si DataCar no responde, no tiene el dominio
                                    o devuelve una clasificación sin traducción. Sólo puede declarar
                                    CAMIONETA (la tarifa más cara): "auto" sale únicamente de DataCar,
                                    así nadie paga como auto teniendo una camioneta.
  4. Verificación del playero    -> en el primer ingreso confirma o corrige.
Ninguna capa bloquea por una API externa: si DataCar falla, el conductor declara.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from integraciones import imagenes
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

CATEGORIAS_DECLARABLES = {Categoria.CAMIONETA}


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
            # Se guardan aunque el tipo no tenga traducción: el conductor ve qué vehículo encontró DataCar
            vehiculo.marca, vehiculo.modelo = resultado.marca, resultado.modelo
            vehiculo.anio, vehiculo.tipo = resultado.anio, resultado.clasificacion[:60]
            foto = imagenes.buscar(resultado.marca, resultado.modelo, resultado.anio)
            vehiculo.imagen_url, vehiculo.imagen_credito = (foto.url, foto.credito) if foto else ("", "")
            if resultado.categoria:  # DataCar prevalece sobre una declaración
                _asignar(vehiculo, resultado.categoria, OrigenCategoria.DATACAR)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en",
                                 "marca", "modelo", "anio", "tipo", "imagen_url", "imagen_credito"])
    return vehiculo


def puede_declarar(vehiculo: Vehiculo) -> bool:
    return not vehiculo.es_moto and vehiculo.categoria_origen is None


@transaction.atomic
def declarar_categoria(vehiculo: Vehiculo, categoria: str) -> Vehiculo:
    """Capa 3: sin dato de DataCar, el conductor acepta reservar con tarifa de camioneta."""
    if categoria not in CATEGORIAS_DECLARABLES:
        raise ValidationError({"categoria": "Sin dato del registro automotor sólo se puede reservar como camioneta."})
    if not puede_declarar(vehiculo):
        raise ValidationError({"categoria": "La categoría de este vehículo ya está definida y no se puede declarar."})
    _asignar(vehiculo, categoria, OrigenCategoria.DECLARADA)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en"])
    return vehiculo


@transaction.atomic
def verificar_por_playero(vehiculo: Vehiculo, categoria_real: str) -> bool:
    """
    Capa 4, en el ingreso: el playero confirma o corrige la categoría. Devuelve True si hubo corrección.
    Como el conductor sólo puede declarar camioneta, una corrección nunca le cobra de más: a lo sumo baja a auto.
    Todavía no tiene endpoint ni pantalla en la app del playero.
    """
    corrigio = vehiculo.categoria != categoria_real
    _asignar(vehiculo, categoria_real, OrigenCategoria.VERIFICADA)
    vehiculo.save(update_fields=["categoria", "categoria_origen", "estado_validacion", "validado_en"])
    return corrigio
