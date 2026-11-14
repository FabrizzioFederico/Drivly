from django.contrib import admin

from .models import Garaje, Resena, Tarifa


class TarifaInline(admin.TabularInline):
    model = Tarifa
    extra = 0


@admin.register(Garaje)
class GarajeAdmin(admin.ModelAdmin):
    list_display = ["nombre", "direccion", "capacidad", "cupo_abonos", "admin", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre", "direccion", "cuit"]
    inlines = [TarifaInline]


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    """Para moderar: borrar una reseña ofensiva la saca del promedio."""

    list_display = ["garaje", "estrellas", "conductor", "creada_en", "respondida_en"]
    list_filter = ["estrellas", "garaje"]
    search_fields = ["comentario", "respuesta", "conductor__email"]
    readonly_fields = ["reserva", "garaje", "conductor", "creada_en", "actualizada_en"]
