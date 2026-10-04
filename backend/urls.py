from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from garajes.views import GarajeViewSet, TarifaViewSet
from vehiculos.views import VehiculoViewSet

router = DefaultRouter()
router.register("garajes", GarajeViewSet, basename="garaje")
router.register("tarifas", TarifaViewSet, basename="tarifa")
router.register("vehiculos", VehiculoViewSet, basename="vehiculo")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("cuentas.urls")),
    path("api/", include(router.urls)),
]
