from django.shortcuts import render
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


def abrir_reserva(request, reserva_id):
    """
    GET /api/notificaciones/reserva/<id>/ — el botón "Ver mi reserva en la app" del comprobante.
    Gmail no deja tocar links drivly://, así que el email apunta acá y esta página abre la app en el ticket.
    No muestra datos de la reserva: la app los pide con la sesión del conductor.
    """
    destino = f"reserva/{reserva_id}"
    return render(request, "notificaciones/abrir_reserva.html", {
        "link_app": f"drivly://{destino}",
        # Chrome en Android abre la app con intent:// aunque no venga de un toque directo
        "link_android": f"intent://{destino}#Intent;scheme=drivly;package=com.drivly.app;end",
    })
