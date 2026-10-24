from reservas.exceptions import GarajeSinMercadoPago  # noqa: F401 — vive en reservas: también lo usa crear_hold


class OAuthError(Exception):
    """Falla de la autorización o del canje de tokens con Mercado Pago. Nunca incluye tokens en el mensaje."""
