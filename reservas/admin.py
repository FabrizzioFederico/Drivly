from django.contrib import admin

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ["id", "garaje", "modalidad", "estado", "periodo", "monto", "creada_en"]
    list_filter = ["estado", "modalidad", "garaje"]
    search_fields = ["id", "vehiculo__patente", "patente_presencial", "conductor__email"]
    readonly_fields = ["qr_token", "creada_en"]
