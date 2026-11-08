from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from cuentas.models import Rol, Usuario

from .models import Garaje, Tarifa


def _validar_con_modelo(instancia, attrs):
    """Reutiliza Model.clean() para no duplicar reglas entre modelo y API."""
    for campo, valor in attrs.items():
        setattr(instancia, campo, valor)
    try:
        instancia.clean()
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.message_dict)


class TarifaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarifa
        fields = [
            "id", "garaje", "categoria", "modalidad",
            "precio_fraccion", "fraccion_min", "minimo_fracciones", "precio_primera_hora", "tope_12h", "tope_24h",
            "precio_periodo", "actualizado_en",
        ]
        read_only_fields = ["id", "actualizado_en"]

    def validate_garaje(self, garaje):
        if garaje.admin_id != self.context["request"].user.id:
            raise serializers.ValidationError("No administrás este garaje.")
        return garaje

    def validate(self, attrs):
        _validar_con_modelo(self.instance or Tarifa(), {**attrs})
        return attrs


class GarajeSerializer(serializers.ModelSerializer):
    """Vista completa, para el admin del garaje y su playero."""

    tarifas = TarifaSerializer(many=True, read_only=True)

    class Meta:
        model = Garaje
        fields = [
            "id", "nombre", "cuit", "direccion", "lat", "lng",
            "capacidad", "cupo_abonos", "tolerancia_min", "salida_estimada_default_min",
            "recargo_overstay", "activo", "tarifas", "creado_en",
        ]
        read_only_fields = ["id", "activo", "tarifas", "creado_en"]

    def validate(self, attrs):
        _validar_con_modelo(self.instance or Garaje(), {**attrs})
        return attrs


class TarifaPublicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarifa
        fields = ["categoria", "modalidad", "precio_fraccion", "fraccion_min", "minimo_fracciones",
                  "precio_primera_hora", "tope_12h", "tope_24h", "precio_periodo"]


class GarajePublicoSerializer(serializers.ModelSerializer):
    """Lo que ve el conductor: sin CUIT ni configuración interna."""

    tarifas = TarifaPublicaSerializer(many=True, read_only=True)
    distancia_m = serializers.SerializerMethodField()

    class Meta:
        model = Garaje
        fields = ["id", "nombre", "direccion", "lat", "lng", "tolerancia_min", "tarifas", "distancia_m"]

    def get_distancia_m(self, garaje):
        valor = getattr(garaje, "distancia_m", None)
        return round(valor) if valor is not None else None


ESTADOS_RESERVA_ACTIVA = ("HOLD", "CONFIRMADA", "EN_CURSO", "CON_DEUDA")


class PlayeroSerializer(serializers.ModelSerializer):
    """
    Alta de playero por su admin, por email:
      - cuenta de conductor existente -> pasa a playero (si no tiene reservas activas ni deuda);
      - email nuevo -> se crea la cuenta y la persona entra con Google usando ese email.
    """

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "is_active"]
        read_only_fields = ["id", "is_active"]
        # Sin el validador de unicidad del modelo: validate_email decide si una cuenta existente puede pasar a playero
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, email):
        email = email.lower()
        existente = Usuario.objects.filter(email=email).first()
        if existente is None:
            return email
        if existente.rol == Rol.PLAYERO and existente.garaje_id is not None:
            raise serializers.ValidationError("Esa persona ya es playero de un garaje.")
        if existente.rol == Rol.ADMIN_GARAJE:
            raise serializers.ValidationError("Ese email es de un administrador: no se puede pasar a playero.")
        # Como playero perdería acceso a su ticket o a pagar su deuda desde la app
        if existente.reservas.filter(estado__in=ESTADOS_RESERVA_ACTIVA).exists():
            raise serializers.ValidationError(
                "Tiene reservas activas o una deuda pendiente como conductor. Pasalo a playero cuando las cierre."
            )
        return email
