from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cuentas.permissions import EsConductor

from .serializers import VehiculoSerializer
from .services import validar_vehiculo


class VehiculoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/vehiculos/ — vehículos del conductor logueado.
    No hay edición: si cambia la patente es otro vehículo.
    """

    serializer_class = VehiculoSerializer
    permission_classes = [IsAuthenticated, EsConductor]

    def get_queryset(self):
        return self.request.user.vehiculos.all()

    def perform_create(self, serializer):
        vehiculo = serializer.save(conductor=self.request.user)
        # Sincrónico por ahora (con el mock es instantáneo). Con patente.ar real,
        # pasarlo a una tarea de Celery y devolver el vehículo en PENDIENTE.
        validar_vehiculo(vehiculo)

    @action(detail=True, methods=["post"])
    def revalidar(self, request, pk=None):
        """Reintento manual cuando quedó PENDIENTE porque patente.ar no respondió."""
        vehiculo = validar_vehiculo(self.get_object())
        return Response(self.get_serializer(vehiculo).data)
