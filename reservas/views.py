from django.conf import settings
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cuentas.models import Rol
from cuentas.permissions import EsConductor

from . import services
from .exceptions import EstadoInvalido
from .models import EstadoReserva, Reserva
from .serializers import HoldSerializer, ReservaSerializer


class ReservaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/reservas/ — conductor: las suyas · admin: las de sus garajes · playero: las de su garaje.
    Filtros: ?estado=HOLD&garaje=<id>
    """

    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = Reserva.objects.select_related("garaje", "vehiculo")
        if u.rol == Rol.ADMIN_GARAJE:
            qs = qs.filter(garaje__admin=u)
        elif u.rol == Rol.PLAYERO:
            qs = qs.filter(garaje_id=u.garaje_id)
        else:
            qs = qs.filter(conductor=u)
        params = self.request.query_params
        if params.get("estado"):
            qs = qs.filter(estado__in=params["estado"].split(","))
        if params.get("garaje"):
            qs = qs.filter(garaje_id=params["garaje"])
        return qs

    def _mia(self):
        reserva = self.get_object()
        if reserva.conductor_id != self.request.user.id:
            raise PermissionDenied("Sólo el conductor de la reserva puede hacer esto.")
        return reserva

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, EsConductor])
    def hold(self, request):
        """POST /api/reservas/hold/ {garaje, vehiculo, modalidad, inicio, fin?} -> HOLD de 5 minutos (CU-04)."""
        datos = HoldSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        reserva, detalle = services.crear_hold(
            request.user, d["garaje"], d["vehiculo"], d["modalidad"], d["inicio"], d.get("fin")
        )
        return Response({**ReservaSerializer(reserva).data, "desglose": detalle}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, EsConductor])
    def cotizar(self, request):
        """
        GET /api/reservas/cotizar/?garaje&vehiculo&modalidad&inicio&fin -> precio estimado, sin retener el lugar.
        Los montos van como texto, igual que `total` en las reservas.
        """
        datos = HoldSerializer(data=request.query_params)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        inicio, fin, detalle = services.cotizar(
            request.user, d["garaje"], d["vehiculo"], d["modalidad"], d["inicio"], d.get("fin")
        )
        return Response({
            "inicio": inicio, "fin": fin, "modalidad": detalle["modalidad"], "total": str(detalle["total"]),
            "fracciones": detalle.get("fracciones"), "fraccion_min": detalle.get("fraccion_min"),
            "precio_fraccion": str(detalle["precio_fraccion"]) if "precio_fraccion" in detalle else None,
            "minimo_aplicado": detalle.get("minimo_aplicado", False),
        })

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """
        POST /api/reservas/{id}/cancelar/ -> reserva + `reembolso`:
        REEMBOLSADO, REEMBOLSO_FALLIDO (se reintenta solo) o null si no había pago (hold o pagos simulados).
        """
        reserva = self._mia()
        estaba_paga = reserva.estado == EstadoReserva.CONFIRMADA
        reserva = services.cancelar(reserva)  # se confirma la cancelación antes de llamar a Mercado Pago
        pago = None
        if estaba_paga:
            from pagos.services import reembolsar_cancelacion
            pago = reembolsar_cancelacion(reserva)
        return Response({**ReservaSerializer(reserva).data, "reembolso": pago.resultado if pago else None})

    @action(detail=True, methods=["post"])
    def pagar(self, request, pk=None):
        """
        Sprint 3: crea preferencia Checkout Pro y devuelve init_point.
        El frontend redirige al usuario al pago en Mercado Pago.
        Con PAGOS_SIMULADOS=True confirma directamente (desarrollo sin credenciales MP).
        """
        reserva = self._mia()

        if settings.DRIVLY_PAGOS_SIMULADOS:
            return Response(ReservaSerializer(services.confirmar_pago(reserva.id)).data)

        if reserva.estado != EstadoReserva.HOLD or reserva.hold_expira <= timezone.now():
            raise EstadoInvalido("La reserva ya no está esperando pago. Volvé a reservar.")

        from pagos.services import CANALES, crear_preferencia
        canal = request.data.get("canal", "web")  # {"canal": "app"} desde la app Android: vuelve por deep link
        if canal not in CANALES:
            raise ValidationError({"canal": f"Debe ser uno de: {', '.join(CANALES)}."})
        return Response({"init_point": crear_preferencia(reserva, canal)})

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        """GET /api/reservas/{id}/qr/ — token estático firmado; la app lo guarda para usarlo sin señal."""
        reserva = self._mia()
        if reserva.estado not in (EstadoReserva.CONFIRMADA, EstadoReserva.EN_CURSO) or not reserva.qr_token:
            raise EstadoInvalido("El QR está disponible sólo para reservas confirmadas o en curso.")
        return Response({
            "qr_token": reserva.qr_token, "valido_desde": reserva.inicio, "valido_hasta": reserva.fin,
            "reutilizable": reserva.es_abono,
        })
