from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cuentas.models import Rol, Usuario
from cuentas.permissions import EsAdminGaraje

from .geo import caja_alrededor, distancia_m
from .models import Garaje, Tarifa
from .serializers import (
    GarajePublicoSerializer,
    GarajeSerializer,
    PlayeroSerializer,
    TarifaSerializer,
)


class GarajeViewSet(viewsets.ModelViewSet):
    """
    /api/garajes/
      Conductor: lista y detalle de garajes activos. Con ?lat=&lng=&radio= ordena por cercanía.
      Admin: CRUD de sus garajes (borrar = desactivar).
      Playero: sólo su garaje.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = Garaje.objects.prefetch_related("tarifas")
        if u.rol == Rol.ADMIN_GARAJE:
            return qs.filter(admin=u)
        if u.rol == Rol.PLAYERO:
            return qs.filter(id=u.garaje_id)
        return qs.filter(activo=True)

    def get_serializer_class(self):
        return GarajePublicoSerializer if self.request.user.rol == Rol.CONDUCTOR else GarajeSerializer

    def get_permissions(self):
        if self.action not in ("list", "retrieve"):
            return [IsAuthenticated(), EsAdminGaraje()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        lat, lng = request.query_params.get("lat"), request.query_params.get("lng")
        if lat is None or lng is None:
            return super().list(request, *args, **kwargs)
        try:
            lat, lng = Decimal(lat), Decimal(lng)
            radio = int(request.query_params.get("radio", settings.DRIVLY_RADIO_CERCANOS_M))
        except (InvalidOperation, ValueError):
            raise ValidationError("lat, lng y radio deben ser numéricos.")
        lat_min, lat_max, lng_min, lng_max = caja_alrededor(lat, lng, radio)
        candidatos = self.get_queryset().filter(
            lat__range=(lat_min, lat_max), lng__range=(lng_min, lng_max)
        )
        cercanos = []
        for garaje in candidatos:
            garaje.distancia_m = distancia_m(lat, lng, garaje.lat, garaje.lng)
            if garaje.distancia_m <= radio:
                cercanos.append(garaje)
        cercanos.sort(key=lambda g: g.distancia_m)
        # TODO Sprint 2: con ?inicio=&fin= filtrar sólo garajes con cupo (ocupación pico < capacidad).
        return Response(self.get_serializer(cercanos, many=True).data)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)

    def destroy(self, request, *args, **kwargs):
        garaje = self.get_object()
        garaje.activo = False  # nunca se borra: tiene reservas e historial asociados
        garaje.save(update_fields=["activo"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activar(self, request, pk=None):
        garaje = self.get_object()
        garaje.activo = True
        garaje.save(update_fields=["activo"])
        return Response(GarajeSerializer(garaje).data)

    @action(detail=True, methods=["get", "post"])
    def playeros(self, request, pk=None):
        garaje = self.get_object()
        if request.method == "GET":
            return Response(PlayeroSerializer(garaje.playeros.all(), many=True).data)
        datos = PlayeroSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            playero = Usuario.objects.filter(email=datos.validated_data["email"]).first()
            if playero:  # playero que quedó sin garaje: se reasigna
                playero.garaje, playero.is_active = garaje, True
                playero.nombre = datos.validated_data.get("nombre") or playero.nombre
                playero.save(update_fields=["garaje", "is_active", "nombre"])
            else:
                playero = Usuario.objects.create_user(
                    email=datos.validated_data["email"],
                    nombre=datos.validated_data.get("nombre", ""),
                    rol=Rol.PLAYERO,
                    garaje=garaje,
                )
        return Response(PlayeroSerializer(playero).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"playeros/(?P<usuario_id>[0-9a-f-]+)")
    def quitar_playero(self, request, pk=None, usuario_id=None):
        garaje = self.get_object()
        playero = get_object_or_404(garaje.playeros, id=usuario_id)
        playero.garaje, playero.is_active = None, False
        playero.save(update_fields=["garaje", "is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TarifaViewSet(viewsets.ModelViewSet):
    """/api/tarifas/?garaje=<id> — sólo el admin, sobre sus propios garajes."""

    serializer_class = TarifaSerializer
    permission_classes = [IsAuthenticated, EsAdminGaraje]

    def get_queryset(self):
        qs = Tarifa.objects.filter(garaje__admin=self.request.user).select_related("garaje")
        garaje = self.request.query_params.get("garaje")
        return qs.filter(garaje_id=garaje) if garaje else qs

    def perform_update(self, serializer):
        if "garaje" in serializer.validated_data and serializer.validated_data["garaje"] != serializer.instance.garaje:
            raise PermissionDenied("Una tarifa no puede cambiar de garaje.")
        serializer.save()
