from django.contrib.auth import authenticate
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import perfil
from .models import Rol, Usuario
from .serializers import (
    ConfirmacionEmailSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    PedidoCambioEmailSerializer,
    RegistroSerializer,
    UsuarioSerializer,
)
from .services import usuario_desde_google, verificar_token_google


def tokens_para(usuario):
    refresh = RefreshToken.for_user(usuario)
    refresh["rol"] = usuario.rol  # el frontend decide qué panel mostrar sin otra llamada
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def respuesta_de_sesion(usuario, estado=status.HTTP_200_OK):
    return Response({**tokens_para(usuario), "user": UsuarioSerializer(usuario).data}, status=estado)


class RegistroView(APIView):
    """POST /api/auth/registro/ {nombre, email, password} -> {access, refresh, user}. Siempre CONDUCTOR."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        datos = RegistroSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario = Usuario.objects.create_user(
            email=datos.validated_data["email"],
            password=datos.validated_data["password"],
            nombre=datos.validated_data["nombre"].strip(),
            rol=Rol.CONDUCTOR,
        )
        return respuesta_de_sesion(usuario, status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ {email, password} -> {access, refresh, user} (mismo formato que Google)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        datos = LoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        # authenticate() rechaza contraseñas inutilizables (cuentas sólo Google) y usuarios inactivos
        usuario = authenticate(
            request,
            email=datos.validated_data["email"].strip().lower(),
            password=datos.validated_data["password"],
        )
        if usuario is None:
            # 401 explícito: AuthenticationFailed sin autenticador configurado sale como 403
            return Response({"detail": "Email o contraseña incorrectos.", "code": "CREDENCIALES_INVALIDAS"},
                            status=status.HTTP_401_UNAUTHORIZED)
        return respuesta_de_sesion(usuario)


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
    """GET/PATCH /api/auth/me/ — datos del usuario logueado. Editables: nombre, género y teléfono."""

    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user


class FotoPerfilView(APIView):
    """PUT /api/auth/me/foto/ (multipart, campo `foto`) la reemplaza; DELETE la quita."""

    parser_classes = [MultiPartParser]

    def put(self, request):
        archivo = request.FILES.get("foto")
        if archivo is None:
            raise ValidationError({"foto": "Elegí una imagen."})
        return Response(UsuarioSerializer(perfil.guardar_foto(request.user, archivo)).data)

    def delete(self, request):
        return Response(UsuarioSerializer(perfil.borrar_foto(request.user)).data)


class CambioEmailView(APIView):
    """POST /api/auth/me/email/ {email} -> manda un código al email nuevo (el cambio todavía no se aplica)."""

    def post(self, request):
        datos = PedidoCambioEmailSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        email = perfil.pedir_cambio_email(request.user, datos.validated_data["email"])
        return Response({"detail": f"Te mandamos un código a {email}."}, status=status.HTTP_202_ACCEPTED)


class ConfirmarEmailView(APIView):
    """POST /api/auth/me/email/confirmar/ {codigo} -> aplica el cambio y devuelve el usuario actualizado."""

    def post(self, request):
        datos = ConfirmacionEmailSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return Response(UsuarioSerializer(perfil.confirmar_cambio_email(request.user, datos.validated_data["codigo"])).data)
