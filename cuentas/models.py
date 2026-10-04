import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    CONDUCTOR = "CONDUCTOR", "Conductor"
    ADMIN_GARAJE = "ADMIN_GARAJE", "Administrador de garaje"
    PLAYERO = "PLAYERO", "Playero"


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
