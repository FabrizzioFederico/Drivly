from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CambioEmailView,
    ConfirmarEmailView,
    DevLoginView,
    FotoPerfilView,
    GoogleLoginView,
    LoginView,
    MeView,
    ReenviarActivacionView,
    RegistroView,
    activar_cuenta,
)

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="auth-google"),
    path("dev-login/", DevLoginView.as_view(), name="auth-dev-login"),
    path("login/", LoginView.as_view(), name="auth-login"),  # email + contraseña
    path("registro/", RegistroView.as_view(), name="auth-registro"),
    path("activar/reenviar/", ReenviarActivacionView.as_view(), name="auth-activar-reenviar"),
    path("activar/<str:uidb64>/<str:token>/", activar_cuenta, name="auth-activar"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/foto/", FotoPerfilView.as_view(), name="auth-me-foto"),
    path("me/email/", CambioEmailView.as_view(), name="auth-me-email"),
    path("me/email/confirmar/", ConfirmarEmailView.as_view(), name="auth-me-email-confirmar"),
]
