from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import DevLoginView, GoogleLoginView, MeView

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="auth-google"),
    path("dev-login/", DevLoginView.as_view(), name="auth-dev-login"),
    path("login/", TokenObtainPairView.as_view(), name="auth-login"),  # email + contraseña
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
]
