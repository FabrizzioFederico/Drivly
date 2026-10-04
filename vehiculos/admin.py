from django.contrib import admin

from .models import ConsultaPatente, Vehiculo


class ConsultaInline(admin.TabularInline):
    model = ConsultaPatente
    extra = 0
    readonly_fields = ["resultado", "respuesta", "consultado_en"]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["patente", "categoria", "estado_validacion", "conductor", "creado_en"]
    list_filter = ["categoria", "estado_validacion"]
    search_fields = ["patente", "conductor__email"]
    inlines = [ConsultaInline]
