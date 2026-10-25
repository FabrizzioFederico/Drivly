from rest_framework import serializers

from .models import Rol, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    # Ruta relativa (/api/media/...): la web y la app la completan con su propio origen (localhost, ngrok, producción)
    foto = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "genero", "telefono", "foto", "rol", "garaje"]
        # El email se cambia con código de verificación (/me/email/) y la foto por /me/foto/
        read_only_fields = ["id", "email", "foto", "rol", "garaje"]

    def get_foto(self, usuario):
        return usuario.foto.url if usuario.foto else None


class PedidoCambioEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ConfirmacionEmailSerializer(serializers.Serializer):
    codigo = serializers.RegexField(r"^\s*\d{6}\s*$", error_messages={"invalid": "El código tiene 6 números."})


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    # Sólo se usa al crear la cuenta: la app manda CONDUCTOR, la web puede mandar ADMIN_GARAJE.
    rol = serializers.ChoiceField(
        choices=[Rol.CONDUCTOR, Rol.ADMIN_GARAJE], default=Rol.CONDUCTOR, required=False
    )
