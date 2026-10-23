from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Usuario
from .serializers import GoogleLoginSerializer, UsuarioSerializer
from .services import usuario_desde_google, verificar_token_google


def tokens_para(usuario):
    refresh = RefreshToken.for_user(usuario)
    refresh["rol"] = usuario.rol  # el frontend decide qué panel mostrar sin otra llamada
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class GoogleLoginView(APIView):
    """POST /api/auth/google/  {id_token, rol?} -> {access, refresh, user}"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        datos = GoogleLoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        info = verificar_token_google(datos.validated_data["id_token"])
        usuario = usuario_desde_google(info, datos.validated_data.get("rol"))
        return Response(
            {**tokens_para(usuario), "user": UsuarioSerializer(usuario).data},
            status=status.HTTP_200_OK,
        )


class DevLoginView(APIView):
    """
    POST /api/auth/dev-login/ { rol? } — solo disponible con DEBUG=True.
    rol: CONDUCTOR (default) | ADMIN_GARAJE | PLAYERO
    Crea o recupera un usuario de prueba por rol sin necesitar Google OAuth.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    _DEV_USERS = {
        "CONDUCTOR":    ("dev.conductor@drivly.local",  "Dev Conductor"),
        "ADMIN_GARAJE": ("fabrizzio.federico@davinci.edu.ar", "Fabrizzio Federico"),
        "PLAYERO":      ("dev.playero@drivly.local",    "Dev Playero"),
    }

    def post(self, request):
        from django.conf import settings
        if not settings.DEBUG:
            return Response({"detail": "Not available in production."}, status=status.HTTP_403_FORBIDDEN)

        rol = request.data.get("rol", "CONDUCTOR").upper()
        if rol not in self._DEV_USERS:
            return Response({"detail": f"Rol inválido: {rol}"}, status=status.HTTP_400_BAD_REQUEST)

        email, nombre = self._DEV_USERS[rol]
        usuario, _ = Usuario.objects.get_or_create(
            email=email,
            defaults={"nombre": nombre, "rol": rol},
        )
        # Si el usuario ya existía con otro rol (ej. CONDUCTOR → ADMIN_GARAJE), lo actualizamos.
        if usuario.rol != rol:
            usuario.rol = rol
            usuario.save(update_fields=["rol"])

        return Response(
            {**tokens_para(usuario), "user": UsuarioSerializer(usuario).data},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — datos del usuario logueado (sólo el nombre es editable)."""

    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
