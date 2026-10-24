"""
Integración con Mercado Pago (split de pagos). Nunca se conecta a MP: el fixture `mp` reemplaza el SDK por un
doble que guarda las preferencias, devuelve los pagos que arma cada test y registra los reembolsos y el token
con el que se creó cada SDK; `token_mp` simula /oauth/token.
"""
import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from freezegun import freeze_time

from garajes.models import Garaje, Tarifa
from pagos import oauth, services
from pagos.models import ConexionMP, EstadoOAuth, Pago, ResultadoPago
from pagos.tasks import reintentar_reembolsos, renovar_conexiones_mp
from reservas.models import EstadoReserva, Modalidad, Reserva
from reservas.services import crear_hold
from reservas.tests import manana, nuevo_conductor


class MPFalso:
    def __init__(self):
        self.pagos = {}
        self.preferencias = []
        self.reembolsos = []
        self.falla_reembolso = False
        self.falla_consulta = False
        self.tokens = []

    def preference(self):
        return SimpleNamespace(create=self._crear_preferencia)

    def payment(self):
        return SimpleNamespace(get=self._consultar)

    def refund(self):
        return SimpleNamespace(create=self._reembolsar)

    def _crear_preferencia(self, datos):
        self.preferencias.append(datos)
        return {"status": 201, "response": {"id": "pref-1", "init_point": "https://mp/checkout"}}

    def _consultar(self, payment_id):
        if self.falla_consulta:
            raise ConnectionError("MP no responde")
        return {"status": 200, "response": self.pagos[str(payment_id)]}

    def _reembolsar(self, payment_id):
        if self.falla_reembolso:
            return {"status": 500, "response": {"message": "internal_error"}}
        self.reembolsos.append(payment_id)
        return {"status": 201, "response": {"id": 9000 + len(self.reembolsos)}}

    def aprobar(self, payment_id, reserva, monto=None, status="approved"):
        self.pagos[str(payment_id)] = {
            "id": payment_id, "status": status, "status_detail": "accredited", "currency_id": "ARS",
            "transaction_amount": float(reserva.monto if monto is None else monto),
            "external_reference": str(reserva.id),
        }


@pytest.fixture
def mp(monkeypatch):
    falso = MPFalso()

    def sdk(token):
        falso.tokens.append(token)
        return falso

    monkeypatch.setattr(services, "_sdk", sdk)
    return falso


class TokenMPFalso:
    """Doble de requests.post contra /oauth/token: guarda cada pedido y devuelve tokens nuevos."""

    def __init__(self):
        self.pedidos = []
        self.falla = False

    def __call__(self, url, data=None, **kwargs):
        assert url == "https://api.mercadopago.com/oauth/token"
        self.pedidos.append(data)
        n = len(self.pedidos)
        if self.falla:
            return SimpleNamespace(status_code=400, json=lambda: {"message": "invalid_grant"})
        return SimpleNamespace(status_code=200, json=lambda: {
            "access_token": f"APP_USR-access-{n}", "refresh_token": f"TG-refresh-{n}", "expires_in": 15552000,
            "user_id": 555, "scope": " ".join(f"urn:mp:online:permiso-{i}/read-write" for i in range(30)),
        })


@pytest.fixture
def token_mp(monkeypatch):
    falso = TokenMPFalso()
    monkeypatch.setattr(oauth.requests, "post", falso)
    return falso


def conectar(garaje, mp_user_id="555", vence_en=timedelta(days=180)):
    conexion = ConexionMP(garaje=garaje, mp_user_id=mp_user_id)
    conexion.guardar_tokens(f"APP_USR-garaje-{mp_user_id}", f"TG-refresh-{mp_user_id}", timezone.now() + vence_en)
    conexion.save()
    return conexion


@pytest.fixture
def garaje(admin_garaje):
    g = Garaje.objects.create(admin=admin_garaje, nombre="Palermo", cuit="30-71234567-1", direccion="Gorriti 4800",
                              lat=Decimal("-34.588"), lng=Decimal("-58.430"), capacidad=1, cupo_abonos=0)
    Tarifa.objects.create(garaje=g, categoria="AUTO", precio_fraccion=Decimal("1000"), fraccion_min=15, minimo_fracciones=1)
    conectar(g)
    return g


def hold(garaje):
    u, v = nuevo_conductor()
    reserva, _ = crear_hold(u, garaje.id, v.id, Modalidad.HORA, manana(14), manana(15))
    return reserva


def firma(data_id, request_id="req-1", ts="1700000000", secreto="secreto-de-tests"):
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    return f"ts={ts},v1={hmac.new(secreto.encode(), manifest.encode(), hashlib.sha256).hexdigest()}"


def notificar(cliente, payment_id, x_signature=None, user_id=555):
    pid = str(payment_id)
    return cliente().post(
        f"/api/pagos/webhook/?data.id={pid}&type=payment",
        {"type": "payment", "data": {"id": pid}, "user_id": user_id}, format="json",
        HTTP_X_SIGNATURE=firma(pid) if x_signature is None else x_signature, HTTP_X_REQUEST_ID="req-1",
    )


# ---------- Preferencia y comisión ----------

def test_preferencia_en_la_cuenta_del_garaje_con_comision(cliente, garaje, mp):
    reserva = hold(garaje)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/")
    assert r.status_code == 200 and r.data == {"init_point": "https://mp/checkout"}
    assert mp.tokens == ["APP_USR-garaje-555"]  # token OAuth del garaje, no el de Drivly
    pref = mp.preferencias[0]
    assert pref["marketplace_fee"] == 400.0 and pref["items"][0]["unit_price"] == 4000.0
    assert "collector_id" not in pref


@pytest.mark.parametrize("monto, comision", [("4000", "400.00"), ("1234.55", "123.46"), ("0.05", "0.01")])
def test_calculo_de_comision(monto, comision):
    assert services.calcular_comision(Decimal(monto)) == Decimal(comision)


def test_garaje_que_se_desconecta_despues_del_hold_no_cobra(cliente, garaje, mp):
    reserva = hold(garaje)
    ConexionMP.objects.all().delete()
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/")
    assert r.status_code == 409 and r.data["code"] == "GARAJE_SIN_MERCADO_PAGO" and mp.preferencias == []


def test_preferencia_vence_con_el_hold_y_excluye_efectivo(cliente, garaje, mp):
    reserva = hold(garaje)
    assert cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/").status_code == 200
    pref = mp.preferencias[0]
    assert pref["expires"] is True and pref["external_reference"] == str(reserva.id)
    assert pref["expiration_date_to"] == timezone.localtime(reserva.hold_expira).isoformat(timespec="milliseconds")
    assert {"id": "ticket"} in pref["payment_methods"]["excluded_payment_types"]


def test_no_se_paga_un_hold_vencido(cliente, garaje, mp):
    reserva = hold(garaje)
    with freeze_time(timezone.now() + timedelta(minutes=6)):
        r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/")
    assert r.status_code == 409 and r.data["code"] == "ESTADO_INVALIDO" and mp.preferencias == []


# ---------- Firma del webhook ----------

@pytest.mark.parametrize("x_signature", ["", "ts=1700000000,v1=deadbeef", firma("123", secreto="otra-clave")])
def test_webhook_rechaza_firma_invalida(cliente, garaje, mp, x_signature):
    reserva = hold(garaje)
    mp.aprobar(123, reserva)
    assert notificar(cliente, 123, x_signature).status_code == 401
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.HOLD and not Pago.objects.exists()


def test_webhook_sin_clave_configurada_rechaza_todo(cliente, garaje, mp, settings):
    settings.MERCADOPAGO_WEBHOOK_SECRET = ""
    assert notificar(cliente, 123).status_code == 401


# ---------- Procesamiento ----------

def test_pago_aprobado_confirma_y_queda_registrado(cliente, garaje, mp):
    reserva = hold(garaje)
    mp.aprobar(123, reserva)
    assert notificar(cliente, 123).status_code == 200
    assert notificar(cliente, 123).status_code == 200  # MP reenvía: no pasa nada nuevo
    reserva.refresh_from_db()
    pago = Pago.objects.get()
    assert reserva.estado == EstadoReserva.CONFIRMADA and reserva.qr_token
    assert (pago.payment_id, pago.monto, pago.resultado) == ("123", Decimal("4000"), ResultadoPago.CONFIRMO_RESERVA)


def test_pago_pendiente_no_confirma(cliente, garaje, mp):
    reserva = hold(garaje)
    mp.aprobar(123, reserva, status="in_process")
    assert notificar(cliente, 123).status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.HOLD and Pago.objects.get().resultado == ResultadoPago.PENDIENTE


def test_monto_distinto_no_confirma(cliente, garaje, mp):
    reserva = hold(garaje)
    mp.aprobar(123, reserva, monto=Decimal("10"))
    assert notificar(cliente, 123).status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.HOLD and Pago.objects.get().resultado == ResultadoPago.MONTO_INCORRECTO
    assert mp.reembolsos == []


def test_pago_tardio_sin_cupo_se_reembolsa(cliente, garaje, mp):
    reserva = hold(garaje)
    with freeze_time(timezone.now() + timedelta(minutes=6)):
        hold(garaje)  # otro conductor toma el único lugar
    mp.aprobar(123, reserva)
    with freeze_time(timezone.now() + timedelta(minutes=7)):
        assert notificar(cliente, 123).status_code == 200
        assert notificar(cliente, 123).status_code == 200  # no reembolsa dos veces
    reserva.refresh_from_db()
    pago = Pago.objects.get()
    assert reserva.estado == EstadoReserva.EXPIRADA and mp.reembolsos == ["123"]
    assert pago.resultado == ResultadoPago.REEMBOLSADO and pago.reembolso_id == "9001"


def test_reembolso_fallido_pide_reintento(cliente, garaje, mp):
    reserva = hold(garaje)
    Reserva.objects.filter(id=reserva.id).update(estado=EstadoReserva.CANCELADA)  # canceló y pagó igual
    mp.aprobar(123, reserva)
    mp.falla_reembolso = True
    assert notificar(cliente, 123).status_code == 500
    assert Pago.objects.get().resultado == ResultadoPago.REEMBOLSO_FALLIDO
    mp.falla_reembolso = False
    assert notificar(cliente, 123).status_code == 200  # reintento de MP
    assert Pago.objects.get().resultado == ResultadoPago.REEMBOLSADO and mp.reembolsos == ["123"]


def test_error_inesperado_se_loguea_y_pide_reintento(cliente, garaje, mp, caplog):
    mp.falla_consulta = True
    assert notificar(cliente, 123).status_code == 500
    assert "Error procesando el pago 123" in caplog.text


def test_pago_ajeno_a_drivly_se_ignora(cliente, garaje, mp):
    mp.pagos["123"] = {"id": 123, "status": "approved", "transaction_amount": 10.0, "external_reference": "otra-cosa"}
    assert notificar(cliente, 123).status_code == 200 and not Pago.objects.exists()


# ---------- Split: de qué cuenta viene el pago ----------

def test_pago_se_consulta_y_reembolsa_con_el_token_del_garaje(cliente, garaje, mp):
    reserva = hold(garaje)
    Reserva.objects.filter(id=reserva.id).update(estado=EstadoReserva.CANCELADA)
    mp.aprobar(123, reserva)
    assert notificar(cliente, 123).status_code == 200
    assert set(mp.tokens) == {"APP_USR-garaje-555"} and mp.reembolsos == ["123"]
    assert Pago.objects.get().comision == Decimal("400.00")


def test_pago_cobrado_por_otro_garaje_no_confirma(cliente, garaje, admin_garaje, mp):
    otro = Garaje.objects.create(admin=admin_garaje, nombre="Otro", cuit="30-71234567-1", direccion="x",
                                 lat=Decimal("-34.6"), lng=Decimal("-58.4"), capacidad=1)
    conectar(otro, mp_user_id="777")
    reserva = hold(garaje)
    mp.aprobar(123, reserva)
    assert notificar(cliente, 123, user_id=777).status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.HOLD and not Pago.objects.exists()


def test_notificacion_de_cuenta_desconocida_pide_reintento(cliente, garaje, mp, caplog):
    assert notificar(cliente, 123, user_id=999).status_code == 500
    assert "sin garaje conectado" in caplog.text


# ---------- OAuth: conexión de la cuenta del garaje ----------

def test_conectar_devuelve_url_de_autorizacion_con_state_de_un_solo_uso(cliente, garaje):
    r = cliente(garaje.admin).post("/api/pagos/oauth/conectar/", {"garaje": str(garaje.id)}, format="json")
    assert r.status_code == 200 and r.data["url"].startswith("https://auth.mercadopago.com/authorization?")
    estado = EstadoOAuth.objects.get()
    for parte in ("client_id=app-de-tests", "response_type=code", "platform_id=mp", f"state={estado.state}",
                  "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fpagos%2Foauth%2Fcallback%2F"):
        assert parte in r.data["url"]
    assert estado.usuario == garaje.admin and estado.garaje == garaje


def test_no_se_conecta_un_garaje_ajeno(cliente, garaje, otro_admin, conductor):
    body = {"garaje": str(garaje.id)}
    assert cliente(otro_admin).post("/api/pagos/oauth/conectar/", body, format="json").status_code == 404
    assert cliente(conductor).post("/api/pagos/oauth/conectar/", body, format="json").status_code == 403


def test_callback_guarda_tokens_cifrados(cliente, garaje, token_mp):
    ConexionMP.objects.all().delete()
    state = oauth.url_autorizacion(garaje.admin, garaje).split("state=")[1]
    r = cliente().get("/api/pagos/oauth/callback/", {"code": "TG-code", "state": state})
    assert r.status_code == 302 and r["Location"] == "http://localhost:5173/?mp_conexion=ok"
    assert token_mp.pedidos[0] == {
        "client_id": "app-de-tests", "client_secret": "client-secret-de-tests", "grant_type": "authorization_code",
        "code": "TG-code", "redirect_uri": "http://localhost:8000/api/pagos/oauth/callback/",
    }
    conexion = ConexionMP.objects.get(garaje=garaje)
    assert conexion.mp_user_id == "555" and conexion.access_token == "APP_USR-access-1"
    assert "APP_USR-access-1" not in conexion.access_token_cifrado and "TG-refresh-1" not in conexion.refresh_token_cifrado
    # El mismo state no sirve dos veces
    r = cliente().get("/api/pagos/oauth/callback/", {"code": "TG-code", "state": state})
    assert r["Location"].endswith("mp_conexion=error") and len(token_mp.pedidos) == 1


@pytest.mark.parametrize("params", [
    {"code": "TG-code", "state": "inventado"},
    {"error": "access_denied", "state": "SE_COMPLETA"},
    {"state": "SE_COMPLETA"},  # sin code
])
def test_callback_rechaza_state_invalido_error_o_sin_code(cliente, garaje, token_mp, params):
    ConexionMP.objects.all().delete()
    state = oauth.url_autorizacion(garaje.admin, garaje).split("state=")[1]
    params = {k: (state if v == "SE_COMPLETA" else v) for k, v in params.items()}
    r = cliente().get("/api/pagos/oauth/callback/", params)
    assert r["Location"].endswith("mp_conexion=error") and not ConexionMP.objects.exists()


def test_callback_con_state_vencido(cliente, garaje, token_mp):
    state = oauth.url_autorizacion(garaje.admin, garaje).split("state=")[1]
    with freeze_time(timezone.now() + timedelta(minutes=11)):
        r = cliente().get("/api/pagos/oauth/callback/", {"code": "TG-code", "state": state})
    assert r["Location"].endswith("mp_conexion=error") and token_mp.pedidos == []


def test_estado_de_la_conexion_no_expone_tokens(cliente, garaje):
    r = cliente(garaje.admin).get("/api/pagos/oauth/estado/", {"garaje": str(garaje.id)})
    assert r.data["conectado"] is True and r.data["requiere_reautorizar"] is False
    assert "token" not in str(r.data).lower()


# ---------- Renovación de tokens ----------

def test_token_por_vencer_se_renueva_y_rota_los_dos(cliente, garaje, mp, token_mp):
    ConexionMP.objects.filter(garaje=garaje).update(expira_en=timezone.now() + timedelta(days=2))
    reserva = hold(garaje)
    assert cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/").status_code == 200
    assert token_mp.pedidos[0]["grant_type"] == "refresh_token" and token_mp.pedidos[0]["refresh_token"] == "TG-refresh-555"
    conexion = ConexionMP.objects.get(garaje=garaje)
    assert (conexion.access_token, conexion.refresh_token) == ("APP_USR-access-1", "TG-refresh-1")
    assert mp.tokens == ["APP_USR-access-1"]


def test_renovacion_rechazada_pide_reautorizar_y_no_usa_otro_token(cliente, garaje, mp, token_mp):
    ConexionMP.objects.filter(garaje=garaje).update(expira_en=timezone.now() + timedelta(days=2))
    token_mp.falla = True
    reserva = hold(garaje)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/")
    assert r.status_code == 409 and r.data["code"] == "GARAJE_SIN_MERCADO_PAGO" and mp.tokens == []
    assert ConexionMP.objects.get(garaje=garaje).requiere_reautorizar
    assert cliente(garaje.admin).get("/api/pagos/oauth/estado/", {"garaje": str(garaje.id)}).data["requiere_reautorizar"]


def test_tarea_diaria_renueva_solo_las_que_vencen(garaje, admin_garaje, token_mp):
    otro = Garaje.objects.create(admin=admin_garaje, nombre="Otro", cuit="30-71234567-1", direccion="x",
                                 lat=Decimal("-34.6"), lng=Decimal("-58.4"), capacidad=1)
    conectar(otro, mp_user_id="777", vence_en=timedelta(days=3))
    assert renovar_conexiones_mp() == 1
    assert ConexionMP.objects.get(garaje=otro).access_token == "APP_USR-access-1"
    assert ConexionMP.objects.get(garaje=garaje).access_token == "APP_USR-garaje-555"


# ---------- Cancelación con reembolso ----------

def reserva_pagada(cliente, garaje, mp, payment_id=123):
    reserva = hold(garaje)
    mp.aprobar(payment_id, reserva)
    assert notificar(cliente, payment_id).status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.CONFIRMADA
    return reserva


def test_cancelar_reserva_pagada_reembolsa_todo(cliente, garaje, mp):
    reserva = reserva_pagada(cliente, garaje, mp)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.status_code == 200 and r.data["estado"] == "CANCELADA" and r.data["reembolso"] == "REEMBOLSADO"
    assert mp.reembolsos == ["123"] and set(mp.tokens) == {"APP_USR-garaje-555"}
    assert Pago.objects.get().resultado == ResultadoPago.REEMBOLSADO


def test_no_se_cancela_dentro_de_las_2_horas_previas(cliente, garaje, mp):
    reserva = reserva_pagada(cliente, garaje, mp)
    with freeze_time(reserva.inicio - timedelta(hours=1, minutes=59)):
        r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.status_code == 409 and "2 h antes del inicio" in r.data["detail"]
    reserva.refresh_from_db()
    assert reserva.estado == EstadoReserva.CONFIRMADA and mp.reembolsos == []


def test_reembolso_de_cancelacion_fallido_se_reintenta_solo(cliente, garaje, mp):
    reserva = reserva_pagada(cliente, garaje, mp)
    mp.falla_reembolso = True
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.data["estado"] == "CANCELADA" and r.data["reembolso"] == "REEMBOLSO_FALLIDO"
    mp.falla_reembolso = False
    assert reintentar_reembolsos() == 1
    assert Pago.objects.get().resultado == ResultadoPago.REEMBOLSADO and mp.reembolsos == ["123"]
    assert reintentar_reembolsos() == 0  # no reembolsa dos veces


def test_reintento_no_reembolsa_una_reserva_que_termino_confirmada(cliente, garaje, mp):
    reserva = reserva_pagada(cliente, garaje, mp)
    Pago.objects.update(resultado=ResultadoPago.REEMBOLSO_FALLIDO)  # el webhook la confirmó al reintentar
    assert reintentar_reembolsos() == 0 and mp.reembolsos == []


def test_cancelar_con_garaje_desconectado_queda_pendiente(cliente, garaje, mp):
    reserva = reserva_pagada(cliente, garaje, mp)
    ConexionMP.objects.update(requiere_reautorizar=True)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.data["estado"] == "CANCELADA" and r.data["reembolso"] == "REEMBOLSO_FALLIDO" and mp.reembolsos == []


def reserva_pagada_en_una_hora(cliente, garaje, mp):
    """Reserva sobre la hora: empieza en 1 h, o sea que ya está dentro del límite de 2 h antes del inicio."""
    u, v = nuevo_conductor()
    ahora = timezone.now()
    reserva, _ = crear_hold(u, garaje.id, v.id, Modalidad.HORA, ahora + timedelta(hours=1), ahora + timedelta(hours=2))
    mp.aprobar(321, reserva)
    assert notificar(cliente, 321).status_code == 200
    reserva.refresh_from_db()
    return reserva


def test_gracia_de_10_minutos_tras_pagar_aunque_falte_menos_de_2_h(cliente, garaje, mp):
    reserva = reserva_pagada_en_una_hora(cliente, garaje, mp)
    datos = cliente(reserva.conductor).get(f"/api/reservas/{reserva.id}/").data
    assert datos["cancelable_hasta"] is not None
    with freeze_time(timezone.now() + timedelta(minutes=9)):
        r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.status_code == 200 and r.data["reembolso"] == "REEMBOLSADO" and mp.reembolsos == ["321"]


def test_pasada_la_gracia_y_dentro_de_las_2_h_no_se_cancela(cliente, garaje, mp):
    reserva = reserva_pagada_en_una_hora(cliente, garaje, mp)
    with freeze_time(timezone.now() + timedelta(minutes=11)):
        r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.status_code == 409 and "10 min siguientes al pago" in r.data["detail"] and mp.reembolsos == []


def test_la_gracia_nunca_pasa_del_inicio(cliente, garaje, mp):
    u, v = nuevo_conductor()
    ahora = timezone.now()
    reserva, _ = crear_hold(u, garaje.id, v.id, Modalidad.HORA, ahora + timedelta(minutes=3), ahora + timedelta(hours=1))
    mp.aprobar(654, reserva)
    notificar(cliente, 654)
    with freeze_time(ahora + timedelta(minutes=4)):  # dentro de la gracia, pero la reserva ya empezó
        r = cliente(u).post(f"/api/reservas/{reserva.id}/cancelar/")
    assert r.status_code == 409 and mp.reembolsos == []


# ---------- Sólo se ofrecen garajes que pueden cobrar ----------

def test_busqueda_y_cercanos_ocultan_garajes_sin_mercado_pago(cliente, garaje, admin_garaje, conductor):
    sin_mp = Garaje.objects.create(admin=admin_garaje, nombre="Sin MP", cuit="30-71234567-1", direccion="Thames 1580",
                                   lat=Decimal("-34.5878"), lng=Decimal("-58.4334"), capacidad=5)
    Tarifa.objects.create(garaje=sin_mp, categoria="AUTO", precio_fraccion=Decimal("900"), fraccion_min=15, minimo_fracciones=1)
    reautorizar = Garaje.objects.create(admin=admin_garaje, nombre="Reautorizar", cuit="30-71234567-1", direccion="x",
                                        lat=Decimal("-34.5879"), lng=Decimal("-58.4300"), capacidad=5)
    Tarifa.objects.create(garaje=reautorizar, categoria="AUTO", precio_fraccion=Decimal("900"), fraccion_min=15, minimo_fracciones=1)
    c = conectar(reautorizar, mp_user_id="888")
    c.requiere_reautorizar = True
    c.save()
    q = {"lat": "-34.5885", "lng": "-58.4305", "inicio": manana(14).isoformat(), "fin": manana(15).isoformat()}
    r = cliente(conductor).get("/api/garajes/disponibles/", q).data
    assert [g["nombre"] for g in r] == ["Palermo"]
    hold(garaje)  # Palermo (capacidad 1) queda lleno: los cercanos tampoco ofrecen garajes que no cobran
    assert cliente(conductor).get(f"/api/garajes/{garaje.id}/cercanos/", q).data == []


def test_no_se_retiene_lugar_en_garaje_sin_mercado_pago(cliente, garaje):
    ConexionMP.objects.all().delete()
    u, v = nuevo_conductor()
    body = {"garaje": str(garaje.id), "vehiculo": str(v.id), "inicio": manana(14).isoformat(), "fin": manana(15).isoformat()}
    r = cliente(u).post("/api/reservas/hold/", body, format="json")
    assert r.status_code == 409 and r.data["code"] == "GARAJE_SIN_MERCADO_PAGO" and not Reserva.objects.exists()


def test_con_pagos_simulados_se_ofrecen_todos(cliente, garaje, conductor, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    ConexionMP.objects.all().delete()
    q = {"lat": "-34.5885", "lng": "-58.4305", "inicio": manana(14).isoformat(), "fin": manana(15).isoformat()}
    assert [g["nombre"] for g in cliente(conductor).get("/api/garajes/disponibles/", q).data] == ["Palermo"]


# ---------- App Android del conductor ----------

def test_pago_desde_la_app_vuelve_por_deep_link(cliente, garaje, mp):
    reserva = hold(garaje)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/", {"canal": "app"}, format="json")
    assert r.status_code == 200 and r.data == {"init_point": "https://mp/checkout"}
    pref = mp.preferencias[0]
    assert pref["back_urls"] == {
        "success": "drivly://pago-resultado?mp_status=success",
        "failure": "drivly://pago-resultado?mp_status=failure",
        "pending": "drivly://pago-resultado?mp_status=pending",
    }
    assert pref["auto_return"] == "approved" and pref["marketplace_fee"] == 400.0


def test_pago_web_sin_url_publica_no_usa_auto_return(cliente, garaje, mp):
    reserva = hold(garaje)
    cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/")
    pref = mp.preferencias[0]
    assert pref["back_urls"]["success"] == "http://localhost:5173/?mp_status=success" and "auto_return" not in pref


def test_canal_invalido(cliente, garaje, mp):
    reserva = hold(garaje)
    r = cliente(reserva.conductor).post(f"/api/reservas/{reserva.id}/pagar/", {"canal": "ios"}, format="json")
    assert r.status_code == 400 and "canal" in r.data and mp.preferencias == []
