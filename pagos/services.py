import mercadopago
from django.conf import settings


def crear_preferencia(reserva) -> str:
    """Crea una preferencia de Checkout Pro y devuelve init_point."""
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    frontend_url = settings.FRONTEND_URL
    backend_url  = settings.BACKEND_URL

    # auto_return solo funciona con URL pública HTTPS
    # MP rechaza la preferencia si back_urls.success es localhost
    es_url_publica = (
        frontend_url.startswith("https://")
        and "localhost" not in frontend_url
        and "127.0.0.1" not in frontend_url
    )

    preference_data = {
        "items": [{
            "title": f"Reserva Drivly · {reserva.garaje.nombre}",
            "quantity": 1,
            "unit_price": float(reserva.monto),
            "currency_id": "ARS",
        }],
        "back_urls": {
            "success": f"{frontend_url}/?mp_status=success",
            "failure": f"{frontend_url}/?mp_status=failure",
            "pending": f"{frontend_url}/?mp_status=pending",
        },
        "external_reference": str(reserva.id),
        "notification_url": f"{backend_url}/api/pagos/webhook/",
        "statement_descriptor": "DRIVLY",
        **({"auto_return": "approved"} if es_url_publica else {}),
    }

    result = sdk.preference().create(preference_data)
    if result["status"] >= 400:
        raise RuntimeError(f"Error creando preferencia MP: {result['response']}")

    return result["response"]["init_point"]
