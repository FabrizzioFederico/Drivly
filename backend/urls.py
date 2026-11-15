from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
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
    path("api/notificaciones/", include("notificaciones.urls")),
]

# Fotos guardadas en media/ (desarrollo, o producción sin Cloudinary): las sirve Django también con DEBUG=False.
# Con Cloudinary las URLs ya apuntan a su CDN y esta ruta no se usa.
urlpatterns += [re_path(rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
