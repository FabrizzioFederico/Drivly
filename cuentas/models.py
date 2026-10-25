import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    CONDUCTOR = "CONDUCTOR", "Conductor"
    ADMIN_GARAJE = "ADMIN_GARAJE", "Administrador de garaje"
    PLAYERO = "PLAYERO", "Playero"


class Genero(models.TextChoices):
    FEMENINO = "FEMENINO", "Femenino"
    MASCULINO = "MASCULINO", "Masculino"
    NO_BINARIO = "NO_BINARIO", "No binario"
    PREFIERO_NO_DECIR = "PREFIERO_NO_DECIR", "Prefiero no decirlo"


validar_telefono = RegexValidator(
    r"^\+?[0-9 ()-]{8,20}$", "Ingresá un teléfono válido, por ejemplo +54 9 11 1234-5678."
)


def ruta_foto(usuario, _nombre_original):
    """Nombre nuevo en cada subida: así ninguna app ni navegador muestra la foto vieja desde su caché."""
    return f"fotos/{usuario.id}/{uuid.uuid4().hex}.jpg"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio.")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()  # usuarios que sólo entran con Google
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        extra.setdefault("rol", Rol.ADMIN_GARAJE)
        return self._crear(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Un único modelo para los tres roles (ver diagrama de clases).
    El playero queda atado a un garaje; conductor y admin no.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=150, blank=True)
    genero = models.CharField(max_length=20, choices=Genero.choices, blank=True, default="")
    telefono = models.CharField(max_length=20, blank=True, default="", validators=[validar_telefono])
    foto = models.ImageField(upload_to=ruta_foto, blank=True, default="")  # 512x512 JPEG (cuentas.perfil)
    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.CONDUCTOR)
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
    garaje = models.ForeignKey(
        "garajes.Garaje",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="playeros",
        help_text="Sólo para playeros.",
    )
    # Regla 3: veces que un playero corrigió una categoría declarada. Con 2 ya no puede declarar.
    correcciones_categoria = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        constraints = [
            # Sólo un playero puede estar vinculado a un garaje.
            models.CheckConstraint(
                name="solo_playero_tiene_garaje",
                condition=models.Q(rol="PLAYERO") | models.Q(garaje__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.nombre or self.email} ({self.get_rol_display()})"

    @property
    def es_conductor(self):
        return self.rol == Rol.CONDUCTOR

    @property
    def es_admin_garaje(self):
        return self.rol == Rol.ADMIN_GARAJE

    @property
    def es_playero(self):
        return self.rol == Rol.PLAYERO

    MAX_CORRECCIONES_CATEGORIA = 2

    @property
    def puede_declarar_categoria(self):
        return self.correcciones_categoria < self.MAX_CORRECCIONES_CATEGORIA


class CambioEmail(models.Model):
    """
    Cambio de email pendiente de confirmar. El email es la identidad de la cuenta: el login con Google vincula
    por email a quien entra por primera vez, así que nunca se cambia sin probar que el nuevo es de quien lo pide.
    """

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="cambio_email")
    email = models.EmailField()
    codigo_hash = models.CharField(max_length=64)  # sha256: el código nunca se guarda en claro
    expira = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
