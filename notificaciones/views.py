from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dispositivo


class DispositivoSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    plataforma = serializers.ChoiceField(choices=["android"], default="android")


class DispositivosView(APIView):
    """
    POST   /api/notificaciones/dispositivos/ {token} — la app registra su token de FCM al ingresar o cuando cambia.
    DELETE /api/notificaciones/dispositivos/ {token} — al cerrar sesión, para que el teléfono no reciba avisos ajenos.
    """

    def post(self, request):
        datos = DispositivoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        # Si el teléfono estaba con otra cuenta, el token pasa a la cuenta nueva
        Dispositivo.objects.update_or_create(
            token=datos.validated_data["token"],
            defaults={"usuario": request.user, "plataforma": datos.validated_data["plataforma"]},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        token = str(request.data.get("token", ""))
        Dispositivo.objects.filter(usuario=request.user, token=token).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
