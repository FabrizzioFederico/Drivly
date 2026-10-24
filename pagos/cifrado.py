"""Cifrado en reposo de los tokens OAuth de los garajes (Fernet: AES-128-CBC + HMAC)."""
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    clave = settings.MERCADOPAGO_TOKEN_ENCRYPTION_KEY
    if not clave:
        raise ImproperlyConfigured(
            "Falta MP_TOKEN_ENCRYPTION_KEY. Generala con: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(clave.encode())


def encrypt_token(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


def decrypt_token(valor: str) -> str:
    return _fernet().decrypt(valor.encode()).decode()
