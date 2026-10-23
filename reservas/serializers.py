from rest_framework import serializers

from .models import Modalidad, Reserva


class GarajeDisponibleSerializer(serializers.Serializer):
    """Forma que espera el frontend en /garajes/disponibles/ y en `cercanos`."""

    id = serializers.UUIDField()
    nombre = serializers.CharField()
    direccion = serializers.CharField()
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    distancia_m = serializers.IntegerField()
    lugares_libres = serializers.IntegerField()
    precio_desde = serializers.DecimalField(max_digits=12, decimal_places=2)
    precio_unidad = serializers.CharField()


class GarajeResumenSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    nombre = serializers.CharField()
    direccion = serializers.CharField()
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)


class ReservaSerializer(serializers.ModelSerializer):
    inicio = serializers.DateTimeField(read_only=True)
    fin = serializers.DateTimeField(read_only=True)
    patente = serializers.CharField(read_only=True)
    origen = serializers.CharField(read_only=True)
    categoria = serializers.CharField(source="categoria_cobrada", read_only=True)
    hold_expira_en = serializers.DateTimeField(source="hold_expira", read_only=True)
    total = serializers.DecimalField(source="monto", max_digits=12, decimal_places=2, read_only=True)
    garaje_detalle = GarajeResumenSerializer(source="garaje", read_only=True)

    class Meta:
        model = Reserva
        fields = [
            "id", "garaje", "garaje_detalle", "vehiculo", "patente", "categoria", "origen", "modalidad",
            "inicio", "fin", "estado", "hold_expira_en", "total", "creada_en",
        ]
        read_only_fields = fields


class HoldSerializer(serializers.Serializer):
    """POST /reservas/hold/ — el conductor manda el vehículo, nunca la categoría (regla 3)."""

    garaje = serializers.UUIDField()
    vehiculo = serializers.UUIDField()
    modalidad = serializers.ChoiceField(
        choices=[Modalidad.HORA, Modalidad.SEMANAL, Modalidad.MENSUAL, Modalidad.ANUAL], default=Modalidad.HORA
    )
    inicio = serializers.DateTimeField()
    fin = serializers.DateTimeField(required=False, allow_null=True, help_text="Sólo HORA; en abonos se calcula.")
