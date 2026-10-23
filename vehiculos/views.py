from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cuentas.permissions import EsConductor

from .serializers import DeclararCategoriaSerializer, VehiculoSerializer
from .services import declarar_categoria, validar_vehiculo


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
        return self.request.user.vehiculos.select_related("conductor")

    def perform_create(self, serializer):
        vehiculo = serializer.save(conductor=self.request.user)
        # Sincrónico con timeout corto: si DataCar no responde, el vehículo queda para declarar.
        validar_vehiculo(vehiculo)

    @action(detail=True, methods=["post"])
    def declarar(self, request, pk=None):
        """POST /api/vehiculos/{id}/declarar/ {categoria: AUTO|CAMIONETA} — respaldo de la regla 3."""
        datos = DeclararCategoriaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        vehiculo = declarar_categoria(self.get_object(), datos.validated_data["categoria"])
        return Response(self.get_serializer(vehiculo).data)

    @action(detail=True, methods=["post"])
    def revalidar(self, request, pk=None):
        """Reintenta DataCar. Si ahora responde, su dato reemplaza a la declaración."""
        vehiculo = validar_vehiculo(self.get_object())
        return Response(self.get_serializer(vehiculo).data)
