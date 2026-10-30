from django.urls import path

from .views import (
    CondonarDeudaView, DeudasDelGarajeView, EfectivoDeudaView, EgresoView, EstadoDeudaView, IngresoView,
    MisDeudasView, PagarDeudaView, SinLugarView,
)

urlpatterns = [
    path("ingreso/", IngresoView.as_view(), name="operacion-ingreso"),
    path("egreso/", EgresoView.as_view(), name="operacion-egreso"),
    path("sin-lugar/", SinLugarView.as_view(), name="operacion-sin-lugar"),
    path("deudas/", DeudasDelGarajeView.as_view(), name="operacion-deudas"),
    path("deudas/<uuid:reserva_id>/", EstadoDeudaView.as_view(), name="operacion-deuda"),
    path("deudas/<uuid:reserva_id>/efectivo/", EfectivoDeudaView.as_view(), name="operacion-deuda-efectivo"),
    path("deudas/<uuid:reserva_id>/condonar/", CondonarDeudaView.as_view(), name="operacion-deuda-condonar"),
    path("mis-deudas/", MisDeudasView.as_view(), name="operacion-mis-deudas"),
    path("mis-deudas/<uuid:reserva_id>/pagar/", PagarDeudaView.as_view(), name="operacion-pagar-deuda"),
]
