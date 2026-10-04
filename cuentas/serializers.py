from rest_framework import serializers

from .models import Rol, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "rol", "garaje"]
        read_only_fields = ["id", "email", "rol", "garaje"]


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    # Sólo se usa al crear la cuenta: la app manda CONDUCTOR, la web puede mandar ADMIN_GARAJE.
    rol = serializers.ChoiceField(
        choices=[Rol.CONDUCTOR, Rol.ADMIN_GARAJE], default=Rol.CONDUCTOR, required=False
    )
