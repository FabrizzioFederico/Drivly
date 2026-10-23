import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Categoria(models.TextChoices):
    AUTO = "AUTO", "Auto"
    MOTO = "MOTO", "Moto"
    CAMIONETA = "CAMIONETA", "Camioneta"


class EstadoValidacion(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Sin categoría (falta declarar)"
    VALIDADO = "VALIDADO", "Con categoría"


class OrigenCategoria(models.TextChoices):
    """De dónde salió la categoría (regla 3, validación en capas)."""

    FORMATO = "FORMATO", "Formato de patente de moto"
    DATACAR = "DATACAR", "DataCar API"
    DECLARADA = "DECLARADA", "Declarada por el conductor"
    VERIFICADA = "VERIFICADA", "Verificada por el playero"


# Formatos de dominio argentinos:
#   auto viejo ABC123 · auto Mercosur AB123CD · moto vieja 123ABC · moto Mercosur A123BCD
PATENTE_RE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2}|\d{3}[A-Z]{3}|[A-Z]\d{3}[A-Z]{3})$")
PATENTE_MOTO_RE = re.compile(r"^(\d{3}[A-Z]{3}|[A-Z]\d{3}[A-Z]{3})$")


def normalizar_patente(valor: str) -> str:
    """'ab 123 cd' / 'AB-123-CD' -> 'AB123CD'."""
    return re.sub(r"[\s\-.]", "", valor or "").upper()


def es_patente_de_moto(valor: str) -> bool:
    return bool(PATENTE_MOTO_RE.match(normalizar_patente(valor)))


def validar_patente(valor: str) -> None:
    if not PATENTE_RE.match(normalizar_patente(valor)):
        raise ValidationError(
            "Patente inválida. Formatos aceptados: ABC123, AB123CD, 123ABC o A123BCD.",
            code="patente_invalida",
        )


class Vehiculo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conductor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehiculos"
    )
    patente = models.CharField(max_length=7, unique=True, validators=[validar_patente])
    # Regla 3: formato de patente, DataCar, declaración o verificación del playero. Nula hasta resolverse.
    categoria = models.CharField(max_length=10, choices=Categoria.choices, null=True, blank=True)
    categoria_origen = models.CharField(max_length=10, choices=OrigenCategoria.choices, null=True, blank=True)
    estado_validacion = models.CharField(
        max_length=10, choices=EstadoValidacion.choices, default=EstadoValidacion.PENDIENTE
    )
    validado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        constraints = [
            models.CheckConstraint(
                name="vehiculo_validado_con_categoria",
                condition=~models.Q(estado_validacion="VALIDADO") | models.Q(categoria__isnull=False),
            ),
            models.CheckConstraint(
                name="vehiculo_categoria_con_origen",
                condition=models.Q(categoria__isnull=True, categoria_origen__isnull=True)
                | models.Q(categoria__isnull=False, categoria_origen__isnull=False),
            ),
        ]

    def save(self, *args, **kwargs):
        self.patente = normalizar_patente(self.patente)
        super().save(*args, **kwargs)

    @property
    def validado(self) -> bool:
        """Tiene categoría y por lo tanto tarifa: puede reservar."""
        return self.estado_validacion == EstadoValidacion.VALIDADO

    @property
    def es_moto(self) -> bool:
        return es_patente_de_moto(self.patente)

    def __str__(self):
        return f"{self.patente} ({self.get_categoria_display() or 'sin categoría'})"


class ConsultaPatente(models.Model):
    """Registro de cada consulta a patente.ar, para auditoría y para depurar fallos."""

    class Resultado(models.TextChoices):
        OK = "OK", "Encontrada"
        NO_ENCONTRADA = "NO_ENCONTRADA", "No encontrada"
        ERROR = "ERROR", "Servicio no disponible"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name="consultas")
    resultado = models.CharField(max_length=15, choices=Resultado.choices)
    respuesta = models.JSONField(default=dict, blank=True)
    consultado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-consultado_en"]
