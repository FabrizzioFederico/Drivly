import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cuentas.models import Rol
from cuentas.permissions import EsAdminGaraje
from garajes.models import Garaje
from garajes.views import _ocupacion
from pagos.services import CANAL_WEB, CANALES, crear_cobro_deuda, reembolsar_cancelacion
from reservas.exceptions import DeudaPatente, GarajeSinMercadoPago
from reservas.serializers import ReservaSerializer
from vehiculos.models import normalizar_patente, validar_patente

from . import services
from .models import ESTADOS_IMPAGOS, Deuda, EstadoDeuda, MedioCobro

logger = logging.getLogger(__name__)


class EsOperador(BasePermission):
    message = "Sólo para playeros y administradores del garaje."

    def has_permission(self, request, view):
        return request.user.rol in (Rol.PLAYERO, Rol.ADMIN_GARAJE)


def _garaje_de(usuario, garaje_id):
    """El playero opera sólo su garaje y el admin los suyos."""
    filtro = {"admin": usuario} if usuario.rol == Rol.ADMIN_GARAJE else {"id": usuario.garaje_id}
    garaje = Garaje.objects.filter(pk=garaje_id, **filtro).first()
    if garaje is None:
        raise NotFound("No operás este garaje.")
    return garaje


class _EscaneoSerializer(serializers.Serializer):
    garaje = serializers.UUIDField()
    qr_token = serializers.CharField(required=False)
    patente = serializers.CharField(required=False)
    salida_estimada = serializers.DateTimeField(required=False)

    def validate_patente(self, valor):
        patente = normalizar_patente(valor)
        validar_patente(patente)
        return patente

    def validate(self, attrs):
        if bool(attrs.get("qr_token")) == bool(attrs.get("patente")):
            raise serializers.ValidationError("Mandá el QR o la patente.")
        return attrs


def _escaneo(request):
    datos = _EscaneoSerializer(data=request.data)
    datos.is_valid(raise_exception=True)
    return _garaje_de(request.user, datos.validated_data["garaje"]), datos.validated_data


def _deuda_json(deuda, mp_qr_data=""):
    # Los montos van como texto, igual que en los serializers: la app Android los espera así.
    return {
        "reserva_id": deuda.reserva_id, "patente": deuda.patente, "minutos_excedidos": deuda.minutos_excedidos,
        "tolerancia_min": deuda.tolerancia_min, "fraccion_min": deuda.fraccion_min, "fracciones": deuda.fracciones,
        "precio_fraccion": str(deuda.precio_fraccion), "recargo": str(deuda.recargo), "total": str(deuda.monto),
        "mp_qr_data": mp_qr_data, "fin_reservado": deuda.reserva.fin, "egreso_real": deuda.egreso_real,
        "garaje_nombre": deuda.reserva.garaje.nombre, "estado": deuda.estado,
        "monto_condonado": str(deuda.monto_condonado), "motivo_condonacion": deuda.motivo_condonacion,
    }


def _qr_de_cobro(deuda):
    """Sin QR igual se puede cobrar en efectivo: un problema con Mercado Pago no frena la salida del auto."""
    if settings.DRIVLY_PAGOS_SIMULADOS:
        return ""
    try:
        return crear_cobro_deuda(deuda)
    except Exception:
        logger.exception("No se pudo crear el cobro de la deuda de la reserva %s", deuda.reserva_id)
        return ""


class _OperacionView(APIView):
    permission_classes = [IsAuthenticated, EsOperador]


class IngresoView(_OperacionView):
    """POST /api/operacion/ingreso/ {garaje, qr_token} | {garaje, patente, salida_estimada} (CU-07, regla 6)"""

    def post(self, request):
        garaje, d = _escaneo(request)
        if not d.get("qr_token") and "salida_estimada" not in d:
            raise serializers.ValidationError({"salida_estimada": "Obligatoria para clientes sin reserva."})
        try:
            if d.get("qr_token"):
                reserva = services.ingreso_con_qr(garaje, d["qr_token"], request.user)
            else:
                reserva = services.ingreso_presencial(garaje, d["patente"], d["salida_estimada"], request.user)
        except DeudaPatente as e:
            deuda = e.extra["deuda"]
            # La deuda es del garaje que la generó: otro garaje sólo la cobra por QR, que se acredita a ese garaje.
            e.extra["deuda"] = {
                **_deuda_json(deuda, _qr_de_cobro(deuda)), "efectivo": deuda.reserva.garaje_id == garaje.id,
            }
            raise
        return Response({"reserva": ReservaSerializer(reserva).data, "ocupacion": _ocupacion(garaje)})


class EgresoView(_OperacionView):
    """POST /api/operacion/egreso/ {garaje, qr_token | patente} (CU-08)"""

    def post(self, request):
        garaje, d = _escaneo(request)
        reserva, deuda = services.egreso(garaje, request.user, d.get("qr_token"), d.get("patente"))
        return Response({
            "reserva": ReservaSerializer(reserva).data,
            "deuda": _deuda_json(deuda, _qr_de_cobro(deuda)) if deuda else None,
            "ocupacion": _ocupacion(garaje),
        })


class SinLugarView(_OperacionView):
    """POST /api/operacion/sin-lugar/ {garaje, qr_token} (regla 6): reembolso, cercanos e incidente."""

    def post(self, request):
        garaje, d = _escaneo(request)
        if not d.get("qr_token"):
            raise serializers.ValidationError({"qr_token": "Escaneá el QR de la reserva."})
        reserva = services.marcar_sin_lugar(garaje, d["qr_token"], request.user)
        pago = reembolsar_cancelacion(reserva)
        ahora = timezone.now()
        cercanos = services.cercanos_serializados(
            garaje, ahora, reserva.fin, reserva.modalidad, reserva.categoria_cobrada
        )
        return Response({
            "reserva": ReservaSerializer(reserva).data,
            "reembolso": {"monto": str(reserva.monto), "estado": pago.resultado if pago else "SIN_PAGO"},
            "cercanos": cercanos,
        })


def _deuda(reserva_id):
    deuda = Deuda.objects.select_related("reserva__garaje").filter(reserva_id=reserva_id).first()
    if deuda is None:
        raise NotFound("Esa reserva no tiene deuda.")
    return deuda


def _deuda_de(usuario, reserva_id):
    deuda = _deuda(reserva_id)
    _garaje_de(usuario, deuda.reserva.garaje_id)
    return deuda


class EstadoDeudaView(_OperacionView):
    """GET /api/operacion/deudas/{reserva_id}/ -> {pagado, transaccion_id} (polling del QR)"""

    def get(self, request, reserva_id):
        deuda = _deuda(reserva_id)
        if not deuda.sigue_a_la_patente:  # pasado el bloqueo la puede estar cobrando cualquier garaje (CP-30)
            _garaje_de(request.user, deuda.reserva.garaje_id)
        return Response({"pagado": deuda.estado == EstadoDeuda.PAGADA, "transaccion_id": deuda.transaccion_id or None})


class EfectivoDeudaView(_OperacionView):
    """POST /api/operacion/deudas/{reserva_id}/efectivo/ — idempotente."""

    def post(self, request, reserva_id):
        services.registrar_efectivo(_deuda_de(request.user, reserva_id))
        return Response({"pagado": True})


class DeudasDelGarajeView(APIView):
    """GET /api/operacion/deudas/?garaje= — lo que le deben al garaje, para reclamar o condonar."""

    permission_classes = [IsAuthenticated, EsAdminGaraje]

    def get(self, request):
        garaje = _garaje_de(request.user, serializers.UUIDField().run_validation(request.query_params.get("garaje")))
        deudas = Deuda.objects.select_related("reserva__garaje").filter(
            reserva__garaje=garaje, estado__in=ESTADOS_IMPAGOS
        )
        return Response([_deuda_json(d) for d in deudas])


class _CondonacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False)


class CondonarDeudaView(APIView):
    """POST /api/operacion/deudas/{reserva_id}/condonar/ {motivo, monto?}: sin monto condona todo el saldo."""

    permission_classes = [IsAuthenticated, EsAdminGaraje]

    def post(self, request, reserva_id):
        datos = _CondonacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        deuda = _deuda_de(request.user, reserva_id)
        services.condonar_deuda(deuda.reserva_id, **datos.validated_data)
        return Response(_deuda_json(_deuda(reserva_id)))


# ---------- Del lado del conductor (CU-09) ----------

def _pendientes_de(conductor):
    return Deuda.objects.select_related("reserva__garaje").filter(
        reserva__conductor=conductor, estado__in=ESTADOS_IMPAGOS
    )


class MisDeudasView(APIView):
    """GET /api/operacion/mis-deudas/ — lo que el conductor debe y le impide reservar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([_deuda_json(d) for d in _pendientes_de(request.user)])


class PagarDeudaView(APIView):
    """
    POST /api/operacion/mis-deudas/{reserva_id}/pagar/ {canal} -> {init_point}
    La deuda se salda cuando llega el webhook. Con PAGOS_SIMULADOS=True se salda directamente.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, reserva_id):
        deuda = _pendientes_de(request.user).filter(reserva_id=reserva_id).first()
        if deuda is None:
            raise NotFound("No tenés esa deuda pendiente.")

        if settings.DRIVLY_PAGOS_SIMULADOS:
            services.saldar_deuda(deuda.reserva_id, MedioCobro.MERCADO_PAGO)
            return Response({"estado": EstadoDeuda.PAGADA})

        canal = request.data.get("canal", CANAL_WEB)
        if canal not in CANALES:
            raise serializers.ValidationError({"canal": f"Debe ser uno de: {', '.join(CANALES)}."})
        try:
            return Response({"init_point": crear_cobro_deuda(deuda, canal)})
        except GarajeSinMercadoPago:  # la deuda sigue siendo con este garaje: no sirve "probá con otro"
            raise GarajeSinMercadoPago("Este garaje no puede cobrar por Mercado Pago ahora. Podés pagarle en persona.")
