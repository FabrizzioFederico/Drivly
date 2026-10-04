from django.contrib import admin

from .models import Garaje, Tarifa


class TarifaInline(admin.TabularInline):
    model = Tarifa
    extra = 0


@admin.register(Garaje)
class GarajeAdmin(admin.ModelAdmin):
    list_display = ["nombre", "direccion", "capacidad", "cupo_abonos", "admin", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre", "direccion", "cuit"]
    inlines = [TarifaInline]
