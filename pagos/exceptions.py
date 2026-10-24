from reservas.exceptions import ReservaError


class GarajeSinMercadoPago(ReservaError):
    default_detail = "Este garaje todavía no puede cobrar con Mercado Pago. Probá con otro garaje."
    default_code = "GARAJE_SIN_MERCADO_PAGO"


class OAuthError(Exception):
    """Falla de la autorización o del canje de tokens con Mercado Pago. Nunca incluye tokens en el mensaje."""
