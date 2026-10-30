from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoMovimiento(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    EGRESO = "EGRESO", "Egreso"


class Movimiento(models.Model):
    """Cada entrada o salida del garaje. Un abono acumula muchos (regla 5). La hora la fija el servidor."""

    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=7, choices=TipoMovimiento.choices)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.reserva_id}"


class EstadoDeuda(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PAGADA = "PAGADA", "Pagada"
    CONDONADA = "CONDONADA", "Condonada"
    INCOBRABLE = "INCOBRABLE", "Incobrable"


# Una deuda incobrable se puede seguir pagando y mantiene suspendida la cuenta: sólo cambia cómo se reporta.
ESTADOS_IMPAGOS = (EstadoDeuda.PENDIENTE, EstadoDeuda.INCOBRABLE)


class MedioCobro(models.TextChoices):
    EFECTIVO = "EFECTIVO", "Efectivo"
    MERCADO_PAGO = "MERCADO_PAGO", "Mercado Pago"


class Deuda(models.Model):
    """Overstay (regla 4). Guarda los valores usados en el cálculo: cambiar la tarifa después no la modifica."""

    reserva = models.OneToOneField("reservas.Reserva", on_delete=models.PROTECT, related_name="deuda")
    patente = models.CharField(max_length=7)
    egreso_real = models.DateTimeField()
    minutos_excedidos = models.PositiveIntegerField()
    tolerancia_min = models.PositiveIntegerField()
    fraccion_min = models.PositiveIntegerField()
    fracciones = models.PositiveIntegerField()
    precio_fraccion = models.DecimalField(max_digits=12, decimal_places=2)
    recargo = models.DecimalField(max_digits=4, decimal_places=2)
    monto = models.DecimalField(max_digits=12, decimal_places=2)  # saldo: una condonación parcial lo reduce
    monto_condonado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    motivo_condonacion = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=10, choices=EstadoDeuda.choices, default=EstadoDeuda.PENDIENTE)
    vence_bloqueo = models.DateTimeField()  # desde acá la deuda sigue también a la patente
    recordatorios_enviados = models.PositiveSmallIntegerField(default=0)
    medio = models.CharField(max_length=12, choices=MedioCobro.choices, blank=True, default="")
    transaccion_id = models.CharField(max_length=32, blank=True, default="")  # payment_id de Mercado Pago
    pagada_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]

    def __str__(self):
        return f"{self.patente} · ${self.monto} · {self.get_estado_display()}"

    @property
    def sigue_a_la_patente(self):
        return self.vence_bloqueo <= timezone.now()


class TipoIncidente(models.TextChoices):
    SIN_LUGAR = "SIN_LUGAR", "Reserva sin lugar físico"


class Incidente(models.Model):
    """Queda registrado contra el garaje que lo generó (regla 6)."""

    garaje = models.ForeignKey("garajes.Garaje", on_delete=models.PROTECT, related_name="incidentes")
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, related_name="incidentes")
    tipo = models.CharField(max_length=9, choices=TipoIncidente.choices)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.garaje}"
