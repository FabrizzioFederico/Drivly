import math
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from vehiculos.models import Categoria


def validar_cuit(valor: str) -> None:
    """CUIT de 11 dígitos con dígito verificador (módulo 11)."""
    digitos = "".join(c for c in valor if c.isdigit())
    if len(digitos) != 11:
        raise ValidationError("El CUIT debe tener 11 dígitos.", code="cuit_invalido")
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    resto = sum(int(d) * p for d, p in zip(digitos[:10], pesos)) % 11
    verificador = 0 if resto == 0 else 9 if resto == 1 else 11 - resto
    if verificador != int(digitos[10]):
        raise ValidationError("El dígito verificador del CUIT no es válido.", code="cuit_invalido")


class Modalidad(models.TextChoices):
    """Modalidades con tarifa. PRESENCIAL se cobra con la tarifa HORA."""

    HORA = "HORA", "Por hora"
    SEMANAL = "SEMANAL", "Abono semanal"
    MENSUAL = "MENSUAL", "Abono mensual"
    ANUAL = "ANUAL", "Abono anual"


class Garaje(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="garajes_administrados",
        limit_choices_to={"rol": "ADMIN_GARAJE"},
    )
    nombre = models.CharField(max_length=120)
    cuit = models.CharField(max_length=13, validators=[validar_cuit])
    direccion = models.CharField(max_length=255)
    lat = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    lng = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    # Capacidad publicada en Drivly (puede ser menor a la física). La comparten app y presenciales.
    capacidad = models.PositiveIntegerField()
    # Máximo de lugares que pueden ocupar abonos semanales/mensuales/anuales (regla 5).
    cupo_abonos = models.PositiveIntegerField(default=0)
    tolerancia_min = models.PositiveIntegerField(default=10)
    # Salida estimada por defecto para clientes presenciales (regla 6).
    salida_estimada_default_min = models.PositiveIntegerField(default=120)
    recargo_overstay = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.50"),
        help_text="0.50 = 50 % de recargo sobre la fracción de overstay.",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(name="capacidad_positiva", condition=Q(capacidad__gt=0)),
            models.CheckConstraint(name="cupo_abonos_valido", condition=Q(cupo_abonos__lte=F("capacidad"))),
            models.CheckConstraint(name="recargo_no_negativo", condition=Q(recargo_overstay__gte=0)),
        ]
        indexes = [models.Index(fields=["lat", "lng"], name="garaje_ubicacion_idx")]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.capacidad is not None and self.cupo_abonos is not None and self.cupo_abonos > self.capacidad:
            raise ValidationError({"cupo_abonos": "No puede superar la capacidad."})


class Tarifa(models.Model):
    """
    Una tarifa por garaje, categoría y modalidad.
    HORA usa fracciones (precio_fraccion, fraccion_min, minimo_fracciones).
    Los abonos usan un precio fijo por período (precio_periodo).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    garaje = models.ForeignKey(Garaje, on_delete=models.CASCADE, related_name="tarifas")
    categoria = models.CharField(max_length=10, choices=Categoria.choices)
    modalidad = models.CharField(max_length=10, choices=Modalidad.choices, default=Modalidad.HORA)
    precio_fraccion = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fraccion_min = models.PositiveIntegerField(null=True, blank=True)
    minimo_fracciones = models.PositiveIntegerField(null=True, blank=True)
    precio_periodo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["garaje", "categoria", "modalidad"]
        constraints = [
            models.UniqueConstraint(
                fields=["garaje", "categoria", "modalidad"], name="tarifa_unica_por_categoria_modalidad"
            ),
            models.CheckConstraint(
                name="tarifa_campos_segun_modalidad",
                condition=(
                    Q(modalidad="HORA", precio_fraccion__gt=0, fraccion_min__gt=0,
                      minimo_fracciones__gte=1, precio_periodo__isnull=True)
                    | (~Q(modalidad="HORA") & Q(precio_periodo__gt=0, precio_fraccion__isnull=True,
                                                fraccion_min__isnull=True, minimo_fracciones__isnull=True))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.garaje} · {self.get_categoria_display()} · {self.get_modalidad_display()}"

    def clean(self):
        errores = {}
        if self.modalidad == Modalidad.HORA:
            for campo in ("precio_fraccion", "fraccion_min", "minimo_fracciones"):
                if not getattr(self, campo):
                    errores[campo] = "Obligatorio para la tarifa por hora."
            if self.precio_periodo is not None:
                errores["precio_periodo"] = "Sólo se usa en abonos."
        else:
            if not self.precio_periodo:
                errores["precio_periodo"] = "Obligatorio para abonos."
            for campo in ("precio_fraccion", "fraccion_min", "minimo_fracciones"):
                if getattr(self, campo) is not None:
                    errores[campo] = "Sólo se usa en la tarifa por hora."
        if errores:
            raise ValidationError(errores)

    def fracciones(self, minutos: int) -> int:
        """Cantidad de fracciones a cobrar: redondeo hacia arriba y nunca menos del mínimo."""
        return max(self.minimo_fracciones, math.ceil(minutos / self.fraccion_min))

    def cotizar(self, inicio, fin) -> Decimal:
        """Precio total de una reserva. El monto se congela en la reserva al crearla."""
        if fin <= inicio:
            raise ValueError("El fin debe ser posterior al inicio.")
        if self.modalidad != Modalidad.HORA:
            return self.precio_periodo
        minutos = math.ceil((fin - inicio).total_seconds() / 60)
        return self.precio_fraccion * self.fracciones(minutos)
