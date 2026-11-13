from django.contrib.auth import authenticate
from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import activacion, perfil
from .models import Rol, Usuario
from .serializers import (
    ConfirmacionEmailSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    PedidoCambioEmailSerializer,
    RegistroSerializer,
    ReenvioActivacionSerializer,
    UsuarioSerializer,
)
from .services import copiar_foto_de_google, usuario_desde_google, verificar_token_google


def tokens_para(usuario):
    refresh = RefreshToken.for_user(usuario)
    refresh["rol"] = usuario.rol  # el frontend decide qué panel mostrar sin otra llamada
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def respuesta_de_sesion(usuario, estado=status.HTTP_200_OK):
    return Response({**tokens_para(usuario), "user": UsuarioSerializer(usuario).data}, status=estado)


class RegistroView(APIView):
    """
    POST /api/auth/registro/ {nombre, email, password} -> 201 {detail, email, email_enviado}.
    La cuenta (siempre CONDUCTOR) queda sin activar hasta que se toca el link del email: no devuelve sesión.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        datos = RegistroSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        email, nombre = datos.validated_data["email"], datos.validated_data["nombre"].strip()
        usuario = Usuario.objects.filter(email__iexact=email).first()
        if usuario is None:
            usuario = Usuario.objects.create_user(
                email=email, password=datos.validated_data["password"], nombre=nombre, rol=Rol.CONDUCTOR,
                email_verificado=False,
            )
        else:  # cuenta pendiente que se vuelve a registrar: los links anteriores dejan de valer
            usuario.nombre = nombre
            usuario.set_password(datos.validated_data["password"])
            usuario.save(update_fields=["nombre", "password"])
        enviado = activacion.enviar(usuario)
        return Response({
            "detail": f"Te mandamos un email a {email}. Tocá el link para activar tu cuenta."
            if enviado else "Creamos tu cuenta, pero no pudimos mandar el email de activación. Pedí que te lo reenviemos.",
            "email": email,
            "email_enviado": enviado,
        }, status=status.HTTP_201_CREATED)


class ReenviarActivacionView(APIView):
    """
    POST /api/auth/activar/reenviar/ {email} -> 202 siempre, exista o no la cuenta (no revela qué emails están
    registrados). Sólo manda el email si la cuenta está pendiente de activación.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        datos = ReenvioActivacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario = Usuario.objects.filter(email__iexact=datos.validated_data["email"].strip(),
                                         email_verificado=False, is_active=True).first()
        if usuario:
            activacion.enviar(usuario)
        return Response({"detail": "Si la cuenta está pendiente de activación, te mandamos un email nuevo."},
                        status=status.HTTP_202_ACCEPTED)


def activar_cuenta(request, uidb64, token):
    """GET /api/auth/activar/<uid>/<token>/ — el link del email. Muestra una página, no JSON: se abre en el navegador."""
    usuario = activacion.activar(uidb64, token)
    return render(request, "cuentas/activada.html", {"ok": usuario is not None}, status=200 if usuario else 400)


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
        # Sólo se avisa con la contraseña correcta: así no se puede averiguar qué emails están registrados
        if not usuario.email_verificado:
            return Response({
                "detail": f"Tu cuenta todavía no está activada. Tocá el link que te mandamos a {usuario.email}.",
                "code": "CUENTA_SIN_ACTIVAR",
            }, status=status.HTTP_403_FORBIDDEN)
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
        copiar_foto_de_google(usuario, info)  # fuera de la transacción: no la deja abierta mientras baja la imagen
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
