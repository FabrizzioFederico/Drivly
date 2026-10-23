from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
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

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        return Response(ReservaSerializer(services.cancelar(self._mia())).data)

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

        from pagos.services import crear_preferencia
        init_point = crear_preferencia(reserva)
        return Response({"init_point": init_point})

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
