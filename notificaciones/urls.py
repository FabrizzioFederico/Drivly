from django.urls import path

from .views import DispositivosView

urlpatterns = [
    path("dispositivos/", DispositivosView.as_view(), name="notificaciones-dispositivos"),
]
