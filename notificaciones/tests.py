"""Comprobantes por email y notificaciones push (Firebase simulado: los tests nunca llaman a FCM)."""
from decimal import Decimal

import pytest
from django.core import mail

from operacion.models import MedioCobro
from operacion.services import saldar_deuda
from operacion.tests import con_deuda, crear_reserva, en, vehiculo  # noqa: F401  (fixture)
from pagos.models import Pago, ResultadoPago
from reservas import services as reservas
from reservas.models import EstadoReserva

from . import push, services
from .models import Aviso, Dispositivo

pytestmark = pytest.mark.django_db
DISPOSITIVOS = "/api/notificaciones/dispositivos/"


class _RespuestaFCM:
    def __init__(self, status, cuerpo=None):
        self.status_code, self.ok, self._cuerpo = status, 200 <= status < 300, cuerpo or {}
        self.text = str(self._cuerpo)

    def json(self):
        return self._cuerpo


@pytest.fixture
def fcm(settings, monkeypatch):
    """FCM simulado: devuelve los mensajes enviados; `respuestas` decide qué contesta por token."""
    settings.FCM_PROJECT_ID = "drivly-test"
    settings.FCM_CREDENCIALES = "cuenta-de-servicio.json"
    monkeypatch.setattr(push, "_token_de_acceso", lambda: "token-oauth")
    enviados, respuestas = [], {}

    def falso_post(url, json, headers, timeout):
        mensaje = json["message"]
        enviados.append({"url": url, **mensaje})
        return respuestas.get(mensaje["token"], _RespuestaFCM(200, {"name": "ok"}))

    monkeypatch.setattr(push.requests, "post", falso_post)
    return enviados, respuestas


def _hold(garaje, vehiculo):  # noqa: F811
    from django.db.backends.postgresql.psycopg_any import DateTimeTZRange

    from reservas.models import Reserva

    return Reserva.objects.create(
        conductor=vehiculo.conductor, garaje=garaje, vehiculo=vehiculo, estado=EstadoReserva.HOLD, hold_expira=en(5),
        periodo=DateTimeTZRange(en(60), en(180)), monto=4000, categoria_cobrada="AUTO",
    )


def _cuerpo_html(correo):
    return correo.alternatives[0][0] if hasattr(correo.alternatives[0], "__getitem__") else correo.alternatives[0].content


# ---------- Formato ----------

@pytest.mark.parametrize("monto, texto", [(4080, "$4.080"), (Decimal("36000.50"), "$36.000,50"), (1119200, "$1.119.200")])
def test_pesos(monto, texto):
    assert services.pesos(monto) == texto


# ---------- Comprobantes ----------

def test_comprobante_de_reserva_sale_una_sola_vez(garaje, vehiculo, conductor):  # noqa: F811
    r = crear_reserva(garaje, vehiculo, en(60), en(180))
    r.confirmada_en = en(0)
    r.save(update_fields=["confirmada_en"])
    Pago.objects.create(reserva=r, payment_id="123456789", estado_mp="approved", monto=4000,
                        resultado=ResultadoPago.CONFIRMO_RESERVA, datos_mp={"payment_type_id": "debit_card"})
    services.reserva_confirmada(r.id)
    services.reserva_confirmada(r.id)  # Mercado Pago avisa el mismo pago varias veces
    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == [conductor.email] and garaje.nombre in correo.subject
    html = _cuerpo_html(correo)
    for texto in ("Reserva confirmada", "$4.000", "123456789", "AB123CD", "Tarjeta de débito", "no es una factura"):
        assert texto in html and texto in correo.body, texto
    assert Aviso.objects.filter(tipo="reserva_confirmada").count() == 2  # email y push (push desactivado igual se registra)


def test_confirmar_el_pago_encola_el_comprobante(garaje, vehiculo, monkeypatch, django_capture_on_commit_callbacks):  # noqa: F811
    from notificaciones import tasks

    encolados = []
    monkeypatch.setattr(tasks.reserva_confirmada, "delay", lambda *a: encolados.append(a))
    r = _hold(garaje, vehiculo)
    with django_capture_on_commit_callbacks(execute=True):
        reservas.confirmar_pago(r.id)
    assert encolados == [(str(r.id),)]


def test_sin_celery_el_aviso_sale_en_el_momento(garaje, vehiculo, monkeypatch, django_capture_on_commit_callbacks):  # noqa: F811
    from notificaciones import tasks

    def sin_broker(*a):
        raise ConnectionError("Redis apagado")

    monkeypatch.setattr(tasks.reserva_confirmada, "delay", sin_broker)
    r = _hold(garaje, vehiculo)
    with django_capture_on_commit_callbacks(execute=True):
        reservas.confirmar_pago(r.id)
    assert len(mail.outbox) == 1  # pagos simulados: el comprobante sale sin operación de Mercado Pago


def test_comprobante_de_deuda_pagada_en_efectivo(garaje, vehiculo, conductor, django_capture_on_commit_callbacks):  # noqa: F811
    r = con_deuda(garaje, vehiculo)
    with django_capture_on_commit_callbacks(execute=True):
        assert saldar_deuda(r.id, MedioCobro.EFECTIVO)
    assert len(mail.outbox) == 1
    html = _cuerpo_html(mail.outbox[0])
    assert "Deuda saldada" in html and "$3.000" in html and "Efectivo" in html and "30 min" in html


def test_comprobante_de_reembolso(garaje, vehiculo, conductor):  # noqa: F811
    r = crear_reserva(garaje, vehiculo, en(60), en(180), EstadoReserva.CANCELADA)
    pago = Pago.objects.create(reserva=r, payment_id="555", estado_mp="approved", monto=4000,
                               resultado=ResultadoPago.REEMBOLSADO, reembolso_id="777")
    services.reembolso(pago.id)
    assert len(mail.outbox) == 1 and "$4.000" in mail.outbox[0].subject
    assert "777" in _cuerpo_html(mail.outbox[0])


def test_si_el_mail_falla_se_puede_reintentar(garaje, vehiculo, monkeypatch):  # noqa: F811
    r = crear_reserva(garaje, vehiculo, en(60), en(180))

    def smtp_caido(*a, **k):
        raise OSError("SMTP caído")

    monkeypatch.setattr(services, "_comprobante", smtp_caido)
    with pytest.raises(OSError):
        services.reserva_confirmada(r.id)
    assert not Aviso.objects.filter(canal="EMAIL").exists()  # la tarea de Celery lo vuelve a intentar
    monkeypatch.undo()
    services.reserva_confirmada(r.id)
    assert len(mail.outbox) == 1


def test_si_el_mail_falla_el_push_sale_igual(fcm, garaje, vehiculo, conductor, monkeypatch):  # noqa: F811
    """Gmail rechaza el login: el conductor igual recibe el push, y el reintento sólo vuelve a probar el email."""
    enviados, _ = fcm
    Dispositivo.objects.create(usuario=conductor, token="tok-1")
    r = crear_reserva(garaje, vehiculo, en(60), en(180))

    def smtp_caido(*a, **k):
        raise OSError("Connection unexpectedly closed")

    monkeypatch.setattr(services, "_comprobante", smtp_caido)
    with pytest.raises(OSError):
        services.reserva_confirmada(r.id)
    assert len(enviados) == 1 and enviados[0]["notification"]["title"] == "Reserva confirmada"
    monkeypatch.setattr(services, "_comprobante", lambda *a, **k: None)
    services.reserva_confirmada(r.id)  # reintento de Celery
    assert len(enviados) == 1  # el push no se repite
    assert set(Aviso.objects.values_list("canal", flat=True)) == {"EMAIL", "PUSH"}


# ---------- Push ----------

def test_registrar_y_borrar_el_telefono(cliente, conductor, crear_usuario):
    c = cliente(conductor)
    assert c.post(DISPOSITIVOS, {"token": "tok-1"}, format="json").status_code == 204
    assert c.post(DISPOSITIVOS, {"token": "tok-1"}, format="json").status_code == 204  # repetido: no duplica
    assert conductor.dispositivos.count() == 1
    # El mismo teléfono con otra cuenta: el token pasa a la cuenta nueva
    otra = crear_usuario("otra@test.com")
    cliente(otra).post(DISPOSITIVOS, {"token": "tok-1"}, format="json")
    assert Dispositivo.objects.get(token="tok-1").usuario == otra
    assert cliente(otra).delete(DISPOSITIVOS, {"token": "tok-1"}, format="json").status_code == 204
    assert not Dispositivo.objects.exists()
    assert cliente().post(DISPOSITIVOS, {"token": "x"}, format="json").status_code == 401


def test_push_de_reserva_confirmada(fcm, garaje, vehiculo, conductor):  # noqa: F811
    enviados, _ = fcm
    Dispositivo.objects.create(usuario=conductor, token="tok-1")
    r = crear_reserva(garaje, vehiculo, en(60), en(180))
    services.reserva_confirmada(r.id)
    assert len(enviados) == 1
    m = enviados[0]
    assert m["url"].endswith("/projects/drivly-test/messages:send") and m["token"] == "tok-1"
    assert m["notification"]["title"] == "Reserva confirmada" and garaje.nombre in m["notification"]["body"]
    assert m["data"] == {"tipo": "reserva", "reserva_id": str(r.id)}


def test_token_invalido_se_borra(fcm, garaje, vehiculo, conductor):  # noqa: F811
    _, respuestas = fcm
    Dispositivo.objects.create(usuario=conductor, token="viejo")
    Dispositivo.objects.create(usuario=conductor, token="nuevo")
    respuestas["viejo"] = _RespuestaFCM(404, {"error": {"details": [{"errorCode": "UNREGISTERED"}]}})
    assert push.enviar(conductor, "Hola", "Prueba") == 1
    assert list(conductor.dispositivos.values_list("token", flat=True)) == ["nuevo"]


def test_recordatorio_de_inicio_y_de_fin(fcm, garaje, vehiculo, conductor):  # noqa: F811
    enviados, _ = fcm
    Dispositivo.objects.create(usuario=conductor, token="tok-1")
    crear_reserva(garaje, vehiculo, en(20), en(140))                    # empieza en 20 min: avisa
    crear_reserva(garaje, vehiculo, en(200), en(260))                   # falta mucho: no
    crear_reserva(garaje, vehiculo, en(-100), en(10), EstadoReserva.EN_CURSO)  # termina en 10 min: avisa
    assert services.recordar_inicios() == 1 and services.recordar_inicios() == 0  # una sola vez
    assert services.avisar_fines() == 1 and services.avisar_fines() == 0
    titulos = [m["notification"]["title"] for m in enviados]
    assert titulos[0].startswith("Tu reserva empieza") and titulos[1].startswith("Tu reserva termina")


def test_sin_firebase_no_se_llama_a_fcm(garaje, vehiculo, conductor, monkeypatch):  # noqa: F811
    def no_llamar(*a, **k):
        raise AssertionError("no tenía que llamar a FCM")

    monkeypatch.setattr(push.requests, "post", no_llamar)
    Dispositivo.objects.create(usuario=conductor, token="tok-1")
    assert push.enviar(conductor, "Hola", "Prueba") == 0
