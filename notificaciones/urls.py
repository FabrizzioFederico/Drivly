from django.urls import path

from .views import DispositivosView, abrir_reserva

urlpatterns = [
    path("dispositivos/", DispositivosView.as_view(), name="notificaciones-dispositivos"),
    path("reserva/<uuid:reserva_id>/", abrir_reserva, name="notificaciones-abrir-reserva"),
]
