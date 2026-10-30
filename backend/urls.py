from django.conf import settings
from django.conf.urls.static import static
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
    path("api/", include("reservas.urls")),
    path("api/pagos/", include("pagos.urls")),
    path("api/operacion/", include("operacion.urls")),
]

# Sólo en desarrollo: en producción los archivos subidos no los sirve Django
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
