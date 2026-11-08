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
    RegistroView,
)

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="auth-google"),
    path("dev-login/", DevLoginView.as_view(), name="auth-dev-login"),
    path("login/", LoginView.as_view(), name="auth-login"),  # email + contraseña
    path("registro/", RegistroView.as_view(), name="auth-registro"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/foto/", FotoPerfilView.as_view(), name="auth-me-foto"),
    path("me/email/", CambioEmailView.as_view(), name="auth-me-email"),
    path("me/email/confirmar/", ConfirmarEmailView.as_view(), name="auth-me-email-confirmar"),
]
