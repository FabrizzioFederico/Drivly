from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import GoogleLoginSerializer, UsuarioSerializer
from .services import usuario_desde_google, verificar_token_google


def tokens_para(usuario):
    refresh = RefreshToken.for_user(usuario)
    refresh["rol"] = usuario.rol  # el frontend decide qué panel mostrar sin otra llamada
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class GoogleLoginView(APIView):
    """POST /api/auth/google/  {id_token, rol?} -> {access, refresh, usuario}"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        datos = GoogleLoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        info = verificar_token_google(datos.validated_data["id_token"])
        usuario = usuario_desde_google(info, datos.validated_data.get("rol"))
        return Response(
            {**tokens_para(usuario), "usuario": UsuarioSerializer(usuario).data},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — datos del usuario logueado (sólo el nombre es editable)."""

    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
