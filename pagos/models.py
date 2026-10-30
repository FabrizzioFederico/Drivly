from django.conf import settings
from django.db import models

from .cifrado import decrypt_token, encrypt_token


class ConexionMP(models.Model):
    """Cuenta de Mercado Pago de un garaje, conectada por OAuth. Los pagos de sus reservas se acreditan ahí."""

    garaje = models.OneToOneField("garajes.Garaje", on_delete=models.CASCADE, related_name="conexion_mp")
    # user_id del vendedor en MP. No es único: un dueño con varios garajes puede usar la misma cuenta.
    mp_user_id = models.CharField(max_length=32, db_index=True)
    access_token_cifrado = models.TextField()
    refresh_token_cifrado = models.TextField()
    expira_en = models.DateTimeField()
    scope = models.TextField(blank=True, default="")  # MP devuelve decenas de permisos: no tiene largo fijo
    # Si el refresh falla hay que volver a autorizar: no se cobra con el token de Drivly como reemplazo.
    requiere_reautorizar = models.BooleanField(default=False)
    conectada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.garaje} · MP {self.mp_user_id}"

    @property
    def access_token(self):
        return decrypt_token(self.access_token_cifrado)

    @property
    def refresh_token(self):
        return decrypt_token(self.refresh_token_cifrado)

    def guardar_tokens(self, access_token, refresh_token, expira_en, scope=""):
        """Reemplaza los dos tokens juntos: MP puede rotar el refresh_token en cada renovación."""
        self.access_token_cifrado = encrypt_token(access_token)
        self.refresh_token_cifrado = encrypt_token(refresh_token)
        self.expira_en = expira_en
        self.scope = scope or ""
        self.requiere_reautorizar = False


class EstadoOAuth(models.Model):
    """`state` de un solo uso que liga el callback de OAuth con el admin y el garaje que lo iniciaron."""

    state = models.CharField(max_length=64, unique=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    garaje = models.ForeignKey("garajes.Garaje", on_delete=models.CASCADE, related_name="+")
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)


class ResultadoPago(models.TextChoices):
    """Qué hizo Drivly con el pago, independiente del estado que informa Mercado Pago."""

    PENDIENTE = "PENDIENTE", "Pendiente (no aprobado todavía)"
    CONFIRMO_RESERVA = "CONFIRMO_RESERVA", "Confirmó la reserva"
    SALDO_DEUDA = "SALDO_DEUDA", "Saldó una deuda de overstay"
    MONTO_INCORRECTO = "MONTO_INCORRECTO", "Monto distinto al de la reserva (revisar)"
    REEMBOLSADO = "REEMBOLSADO", "Reembolsado"
    REEMBOLSO_FALLIDO = "REEMBOLSO_FALLIDO", "Reembolso fallido (se reintenta)"


class Pago(models.Model):
    """Un pago de Mercado Pago. Sin este registro no se puede reembolsar, conciliar ni cobrar deudas."""

    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="pagos")
    payment_id = models.CharField(max_length=32, unique=True)  # id del pago en Mercado Pago
    estado_mp = models.CharField(max_length=32)  # approved, pending, rejected, refunded...
    estado_detalle_mp = models.CharField(max_length=64, blank=True, default="")
    monto = models.DecimalField(max_digits=12, decimal_places=2)  # lo que pagó el conductor según MP
    comision = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # marketplace_fee retenido por Drivly
    resultado = models.CharField(max_length=20, choices=ResultadoPago.choices, default=ResultadoPago.PENDIENTE)
    reembolso_id = models.CharField(max_length=32, blank=True, default="")
    datos_mp = models.JSONField(default=dict)  # respuesta completa de MP, para conciliar
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"MP {self.payment_id} · {self.estado_mp} · {self.get_resultado_display()}"
