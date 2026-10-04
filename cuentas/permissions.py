from rest_framework.permissions import BasePermission

from .models import Rol


class _TieneRol(BasePermission):
    rol = None

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == self.rol)


class EsConductor(_TieneRol):
    rol = Rol.CONDUCTOR
    message = "Sólo para conductores."


class EsAdminGaraje(_TieneRol):
    rol = Rol.ADMIN_GARAJE
    message = "Sólo para administradores de garaje."


class EsPlayero(_TieneRol):
    rol = Rol.PLAYERO
    message = "Sólo para playeros."
