"""Perfil del usuario: foto y cambio de email verificado por código."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from .models import CambioEmail, Usuario

LADO_FOTO = 512
MAX_FOTO_MB = 5
VIGENCIA_CODIGO = timedelta(minutes=15)
MAX_INTENTOS = 5


# ---------- Foto ----------

def guardar_foto(usuario, archivo):
    """
    Recorta al centro en cuadrado, corrige la rotación de la cámara (EXIF), achica a 512 px y guarda JPEG.
    Una foto de varios MB del teléfono queda en unas decenas de KB. Borra la foto anterior.
    """
    if archivo.size > MAX_FOTO_MB * 1024 * 1024:
        raise ValidationError({"foto": f"La foto no puede pesar más de {MAX_FOTO_MB} MB."})
    try:
        imagen = Image.open(archivo)
        imagen.verify()  # detecta archivos truncados o que no son imágenes
        archivo.seek(0)
        imagen = ImageOps.exif_transpose(Image.open(archivo))
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError({"foto": "El archivo no es una imagen válida (JPG, PNG o WebP)."})

    imagen = ImageOps.fit(imagen.convert("RGB"), (LADO_FOTO, LADO_FOTO), Image.Resampling.LANCZOS)
    salida = BytesIO()
    imagen.save(salida, format="JPEG", quality=85, optimize=True)

    anterior = usuario.foto.name
    usuario.foto.save("foto.jpg", ContentFile(salida.getvalue()), save=True)  # el nombre real lo pone ruta_foto
    if anterior:
        usuario.foto.storage.delete(anterior)
    return usuario


def borrar_foto(usuario):
    if usuario.foto:
        usuario.foto.delete(save=True)
    return usuario


# ---------- Cambio de email ----------

def _hash(codigo: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), codigo.encode(), hashlib.sha256).hexdigest()


def pedir_cambio_email(usuario, email: str):
    """Manda un código de 6 dígitos al email nuevo. El cambio se aplica recién al confirmarlo."""
    email = Usuario.objects.normalize_email(email).lower()
    if email == usuario.email:
        raise ValidationError({"email": "Ese ya es tu email."})
    if Usuario.objects.filter(email=email).exclude(pk=usuario.pk).exists():
        raise ValidationError({"email": "Ese email ya está en uso en otra cuenta de Drivly."})
    codigo = f"{secrets.randbelow(10**6):06d}"
    CambioEmail.objects.update_or_create(
        usuario=usuario,
        defaults={"email": email, "codigo_hash": _hash(codigo), "expira": timezone.now() + VIGENCIA_CODIGO, "intentos": 0},
    )
    minutos = int(VIGENCIA_CODIGO.total_seconds() // 60)
    send_mail(
        subject=f"Drivly: tu código es {codigo}",
        message=(
            f"Hola{(' ' + usuario.nombre) if usuario.nombre else ''}:\n\n"
            f"Tu código para confirmar este email en Drivly es {codigo}. Vence en {minutos} minutos.\n\n"
            "Si no pediste cambiar tu email, ignorá este mensaje: tu cuenta no cambia."
        ),
        from_email=None,
        recipient_list=[email],
    )
    return email


def confirmar_cambio_email(usuario, codigo: str):
    # El error se lanza fuera de la transacción: si se lanzara adentro, el rollback desharía también el
    # contador de intentos fallidos y el límite contra fuerza bruta nunca se alcanzaría.
    error = _confirmar(usuario, (codigo or "").strip())
    if error:
        raise ValidationError(error)
    return usuario


@transaction.atomic
def _confirmar(usuario, codigo):
    """Aplica el cambio o devuelve el error, dejando guardado lo que corresponda (intentos, borrado)."""
    pendiente = CambioEmail.objects.select_for_update().filter(usuario=usuario).first()
    if pendiente is None:
        return {"codigo": "No hay un cambio de email pendiente. Pedí un código nuevo."}
    if pendiente.expira <= timezone.now() or pendiente.intentos >= MAX_INTENTOS:
        pendiente.delete()
        return {"codigo": "El código venció o tuvo demasiados intentos. Pedí uno nuevo."}
    if not hmac.compare_digest(pendiente.codigo_hash, _hash(codigo)):
        pendiente.intentos += 1
        pendiente.save(update_fields=["intentos"])
        return {"codigo": "El código no es correcto."}
    if Usuario.objects.filter(email=pendiente.email).exclude(pk=usuario.pk).exists():  # lo tomó otra cuenta
        pendiente.delete()
        return {"email": "Ese email ya está en uso en otra cuenta de Drivly."}
    usuario.email = pendiente.email
    usuario.save(update_fields=["email"])
    pendiente.delete()
    return None
