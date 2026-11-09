import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.shortcuts import render
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dispositivo

logger = logging.getLogger(__name__)


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


class ContactoSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    garaje = serializers.CharField(max_length=150)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    zona = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    mensaje = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    # Trampa para bots: el formulario lo deja oculto y vacío. Si viene completo, se descarta sin avisar.
    sitio_web = serializers.CharField(required=False, allow_blank=True, default="")


class ContactoView(APIView):
    """
    POST /api/notificaciones/contacto/ — formulario "Sumá tu garaje" de la landing. Le llega un email al equipo
    (DRIVLY_CONTACTO_EMAIL) con "Responder" apuntando al interesado. Sin sesión; 5 envíos por hora por IP.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "contacto"

    def post(self, request):
        datos = ContactoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        d = datos.validated_data
        if d["sitio_web"]:
            return Response(status=status.HTTP_202_ACCEPTED)  # bot: se descarta
        if not settings.DRIVLY_CONTACTO_EMAIL:
            logger.error("Llegó un contacto de la landing pero falta DRIVLY_CONTACTO_EMAIL en el .env")
            return Response({"detail": "No pudimos enviar tu mensaje. Probá de nuevo más tarde."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        cuerpo = "\n".join([
            "Un garaje quiere sumarse a Drivly (formulario de la landing).",
            "",
            f"Nombre: {d['nombre']}",
            f"Email: {d['email']}",
            f"Teléfono: {d['telefono'] or '—'}",
            f"Garaje: {d['garaje']}",
            f"Zona: {d['zona'] or '—'}",
            "",
            d["mensaje"] or "(sin mensaje)",
        ])
        try:
            EmailMessage(subject=f"Drivly: {d['garaje']} quiere sumarse", body=cuerpo,
                         to=[settings.DRIVLY_CONTACTO_EMAIL], reply_to=[d["email"]]).send()
        except Exception:
            logger.exception("No se pudo enviar el contacto de la landing")
            return Response({"detail": "No pudimos enviar tu mensaje. Probá de nuevo más tarde."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "¡Gracias! Te escribimos en menos de 48 horas hábiles."}, status=status.HTTP_201_CREATED)
