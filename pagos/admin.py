from django.contrib import admin

from .models import ConexionMP, Pago


@admin.register(ConexionMP)
class ConexionMPAdmin(admin.ModelAdmin):
    list_display = ("garaje", "mp_user_id", "expira_en", "requiere_reautorizar", "conectada_en")
    list_filter = ("requiere_reautorizar",)
    exclude = ("access_token_cifrado", "refresh_token_cifrado")  # nunca mostrar tokens
    readonly_fields = ("garaje", "mp_user_id", "expira_en", "scope", "conectada_en", "actualizada_en")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "reserva", "estado_mp", "monto", "resultado", "creado_en")
    list_filter = ("resultado", "estado_mp")
    search_fields = ("payment_id", "reserva__id")
    readonly_fields = ("datos_mp", "creado_en", "actualizado_en")
