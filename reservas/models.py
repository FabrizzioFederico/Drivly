import uuid

from django.conf import settings
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.indexes import GistIndex
from django.db import models
from django.db.models import Q

from vehiculos.models import Categoria


class Modalidad(models.TextChoices):
    HORA = "HORA", "Por hora"
    SEMANAL = "SEMANAL", "Abono semanal"
    MENSUAL = "MENSUAL", "Abono mensual"
    ANUAL = "ANUAL", "Abono anual"
    PRESENCIAL = "PRESENCIAL", "Cliente sin reserva"


MODALIDADES_ABONO = (Modalidad.SEMANAL, Modalidad.MENSUAL, Modalidad.ANUAL)


class EstadoReserva(models.TextChoices):
    HOLD = "HOLD", "Retenida (esperando pago)"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    EN_CURSO = "EN_CURSO", "En curso"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CON_DEUDA = "CON_DEUDA", "Con deuda"
    EXPIRADA = "EXPIRADA", "Expirada"
    CANCELADA = "CANCELADA", "Cancelada"
    NO_SHOW = "NO_SHOW", "No se presentó"
    SIN_LUGAR = "SIN_LUGAR", "Sin lugar físico"


# Estados que ocupan capacidad (regla 1). Un HOLD sólo ocupa mientras no venció.
ESTADOS_OCUPAN = (EstadoReserva.HOLD, EstadoReserva.CONFIRMADA, EstadoReserva.EN_CURSO)


class Reserva(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conductor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reservas"
    )
    garaje = models.ForeignKey("garajes.Garaje", on_delete=models.PROTECT, related_name="reservas")
    vehiculo = models.ForeignKey(
        "vehiculos.Vehiculo", on_delete=models.PROTECT, null=True, blank=True, related_name="reservas"
    )
    modalidad = models.CharField(max_length=10, choices=Modalidad.choices, default=Modalidad.HORA)
    # Intervalo semiabierto [inicio, fin) en UTC: una reserva que termina 16:00 no choca con otra que empieza 16:00.
    periodo = DateTimeRangeField()
    estado = models.CharField(max_length=10, choices=EstadoReserva.choices, default=EstadoReserva.HOLD)
    hold_expira = models.DateTimeField(null=True, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # congelado al crear (regla 3)
    categoria_cobrada = models.CharField(max_length=10, choices=Categoria.choices, null=True, blank=True)
    # Cliente presencial (regla 6): sin conductor ni vehículo registrados
    patente_presencial = models.CharField(max_length=7, blank=True, default="")
    salida_estimada = models.DateTimeField(null=True, blank=True)
    suscripcion_mp_id = models.CharField(max_length=64, blank=True, default="")
    qr_token = models.CharField(max_length=128, unique=True, null=True, blank=True)
    confirmada_en = models.DateTimeField(null=True, blank=True)  # cuándo se acreditó el pago (gracia para cancelar)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        constraints = [
            models.CheckConstraint(
                name="periodo_valido",
                condition=Q(periodo__isempty=False, periodo__lower_inf=False, periodo__upper_inf=False),
            ),
            models.CheckConstraint(
                name="hold_con_vencimiento", condition=~Q(estado="HOLD") | Q(hold_expira__isnull=False)
            ),
            models.CheckConstraint(
                name="origen_coherente",
                condition=(
                    Q(modalidad="PRESENCIAL", conductor__isnull=True, vehiculo__isnull=True,
                      salida_estimada__isnull=False) & ~Q(patente_presencial="")
                )
                | (~Q(modalidad="PRESENCIAL") & Q(conductor__isnull=False, vehiculo__isnull=False)),
            ),
        ]
        indexes = [
            # Búsqueda de solapamientos por garaje (requiere la extensión btree_gist)
            GistIndex(
                fields=["garaje", "periodo"], name="reserva_garaje_periodo_gist",
                condition=Q(estado__in=["HOLD", "CONFIRMADA", "EN_CURSO"]),
            ),
            models.Index(fields=["estado", "hold_expira"], name="reserva_hold_expira_idx"),
        ]

    def __str__(self):
        return f"{self.id} · {self.patente} · {self.get_estado_display()}"

    @property
    def inicio(self):
        return self.periodo.lower

    @property
    def fin(self):
        return self.periodo.upper

    @property
    def patente(self):
        return self.vehiculo.patente if self.vehiculo_id else self.patente_presencial

    @property
    def es_abono(self):
        return self.modalidad in MODALIDADES_ABONO

    @property
    def origen(self):
        return "PRESENCIAL" if self.modalidad == Modalidad.PRESENCIAL else "APP"
