"""Casos de prueba de la documentación (sección 15) para ingreso, egreso, overstay y presenciales."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone
from freezegun import freeze_time

from cuentas.models import Rol
from garajes.models import Garaje, Tarifa
from pagos.models import Pago, ResultadoPago
from pagos.services import procesar_notificacion_pago
from pagos.tests import conectar, mp  # noqa: F401  (fixture)
from reservas import services as reservas
from reservas.models import EstadoReserva, Modalidad, Reserva
from vehiculos.models import Vehiculo

from .models import Deuda, EstadoDeuda, Incidente, MedioCobro, Movimiento, TipoMovimiento

pytestmark = pytest.mark.django_db

INGRESO, EGRESO, SIN_LUGAR = "/api/operacion/ingreso/", "/api/operacion/egreso/", "/api/operacion/sin-lugar/"
AHORA = "2026-10-23 15:00:00-03:00"


@pytest.fixture(autouse=True)
def tarifa_hora(garaje):
    garaje.tolerancia_min = 10
    garaje.recargo_overstay = Decimal("0.50")
    garaje.save()
    return Tarifa.objects.create(
        garaje=garaje, categoria="AUTO", modalidad="HORA", precio_fraccion=1000, fraccion_min=15, minimo_fracciones=1
    )


@pytest.fixture
def playero(crear_usuario, garaje):
    return crear_usuario("pepe@test.com", rol=Rol.PLAYERO, garaje=garaje)


@pytest.fixture
def vehiculo(conductor):
    return Vehiculo.objects.create(conductor=conductor, patente="AB123CD", categoria="AUTO",
                                   categoria_origen="DATACAR", estado_validacion="VALIDADO")


def crear_reserva(garaje, vehiculo, inicio, fin, estado=EstadoReserva.CONFIRMADA, modalidad=Modalidad.HORA):
    r = Reserva.objects.create(
        conductor=vehiculo.conductor, garaje=garaje, vehiculo=vehiculo, modalidad=modalidad, estado=estado,
        periodo=DateTimeTZRange(inicio, fin), monto=4000, categoria_cobrada="AUTO",
    )
    r.qr_token = reservas.generar_qr_token(r)
    r.save(update_fields=["qr_token"])
    return r


def en(minutos):
    return timezone.now() + timedelta(minutes=minutos)


def escanear(c, url, garaje, reserva):
    return c.post(url, {"garaje": str(garaje.id), "qr_token": reserva.qr_token}, format="json")


def test_ingreso_con_qr_pasa_a_en_curso(cliente, playero, garaje, vehiculo):
    r = crear_reserva(garaje, vehiculo, en(0), en(60))
    res = escanear(cliente(playero), INGRESO, garaje, r)
    assert res.status_code == 200 and res.data["reserva"]["estado"] == "EN_CURSO"
    assert res.data["ocupacion"]["ocupados_app"] == 1
    assert Movimiento.objects.filter(reserva=r, tipo=TipoMovimiento.INGRESO, registrado_por=playero).exists()


def test_no_se_entra_antes_de_la_tolerancia_ni_dos_veces(cliente, playero, garaje, vehiculo):
    c = cliente(playero)
    temprano = crear_reserva(garaje, vehiculo, en(30), en(90))
    assert escanear(c, INGRESO, garaje, temprano).status_code == 409
    a_tiempo = crear_reserva(garaje, vehiculo, en(-5), en(-1 + 60))
    assert escanear(c, INGRESO, garaje, a_tiempo).status_code == 200
    assert escanear(c, INGRESO, garaje, a_tiempo).status_code == 409


def test_cp21_qr_de_otro_garaje_se_rechaza_sin_cambios(cliente, otro_admin, playero, garaje, vehiculo):
    otro = Garaje.objects.create(admin=otro_admin, nombre="B", cuit=garaje.cuit, direccion="x",
                                 lat=garaje.lat, lng=garaje.lng, capacidad=5)
    r = crear_reserva(otro, vehiculo, en(0), en(60))
    assert escanear(cliente(playero), INGRESO, garaje, r).status_code == 400
    r.refresh_from_db()
    assert r.estado == EstadoReserva.CONFIRMADA


def test_playero_no_opera_otro_garaje(cliente, otro_admin, playero, garaje, vehiculo):
    otro = Garaje.objects.create(admin=otro_admin, nombre="B", cuit=garaje.cuit, direccion="x",
                                 lat=garaje.lat, lng=garaje.lng, capacidad=5)
    r = crear_reserva(otro, vehiculo, en(0), en(60))
    assert escanear(cliente(playero), INGRESO, otro, r).status_code == 404


def test_conductor_no_puede_operar(cliente, conductor, garaje, vehiculo):
    r = crear_reserva(garaje, vehiculo, en(0), en(60))
    assert escanear(cliente(conductor), INGRESO, garaje, r).status_code == 403


def test_qr_adulterado_se_rechaza(cliente, playero, garaje):
    res = cliente(playero).post(INGRESO, {"garaje": str(garaje.id), "qr_token": "drivly.v1.falso.firma"}, format="json")
    assert res.status_code == 400


def test_cp17_egreso_dentro_de_tolerancia(cliente, playero, garaje, vehiculo):
    with freeze_time(AHORA):
        r = crear_reserva(garaje, vehiculo, en(-60), en(-8), EstadoReserva.EN_CURSO)
        res = escanear(cliente(playero), EGRESO, garaje, r)
    assert res.data["reserva"]["estado"] == "FINALIZADA" and res.data["deuda"] is None


def test_cp18_overstay_genera_deuda_y_bloquea_al_conductor(cliente, playero, garaje, vehiculo, conductor, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    with freeze_time(AHORA):
        r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
        res = escanear(cliente(playero), EGRESO, garaje, r)
    d = res.data["deuda"]
    assert res.data["reserva"]["estado"] == "CON_DEUDA"
    assert (d["minutos_excedidos"], d["fracciones"], d["total"]) == (30, 2, Decimal("3000.00"))
    assert d["recargo"] == Decimal("0.50") and d["mp_qr_data"] == ""
    assert reservas.tiene_deuda(conductor)


def test_cobro_en_efectivo_salda_la_deuda(cliente, playero, garaje, vehiculo, conductor):
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
    c = cliente(playero)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("operacion.views.crear_cobro_deuda", lambda d: "https://mp/deuda")
        res = escanear(c, EGRESO, garaje, r)
    assert res.data["deuda"]["mp_qr_data"] == "https://mp/deuda"
    url = f"/api/operacion/deudas/{r.id}/"
    assert c.get(url).data["pagado"] is False
    assert c.post(f"{url}efectivo/").status_code == 200
    assert c.post(f"{url}efectivo/").status_code == 200  # idempotente
    assert c.get(url).data["pagado"] is True
    r.refresh_from_db()
    assert r.estado == EstadoReserva.FINALIZADA and not reservas.tiene_deuda(conductor)
    assert Deuda.objects.get(reserva=r).medio == MedioCobro.EFECTIVO


def test_si_mercado_pago_falla_igual_sale_con_deuda(cliente, playero, garaje, vehiculo, monkeypatch):
    def falla(deuda):
        raise ConnectionError("MP no responde")

    monkeypatch.setattr("operacion.views.crear_cobro_deuda", falla)
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
    res = escanear(cliente(playero), EGRESO, garaje, r)
    assert res.status_code == 200 and res.data["deuda"]["mp_qr_data"] == ""


def _pago_deuda(mp, payment_id, deuda, monto=None):
    mp.pagos[str(payment_id)] = {
        "id": payment_id, "status": "approved", "status_detail": "accredited", "currency_id": "ARS",
        "transaction_amount": float(deuda.monto if monto is None else monto),
        "external_reference": f"deuda:{deuda.reserva_id}",
    }


def test_webhook_salda_la_deuda_con_su_monto_y_comision(cliente, playero, garaje, vehiculo, mp):  # noqa: F811
    conectar(garaje)
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
    res = escanear(cliente(playero), EGRESO, garaje, r)
    assert res.data["deuda"]["mp_qr_data"] == "https://mp/checkout"
    assert mp.preferencias[-1]["external_reference"] == f"deuda:{r.id}"
    deuda = Deuda.objects.get(reserva=r)
    assert mp.preferencias[-1]["marketplace_fee"] == float(deuda.monto) * 0.10

    _pago_deuda(mp, 77, deuda)
    pago = procesar_notificacion_pago(77, "555")
    deuda.refresh_from_db()
    r.refresh_from_db()
    assert pago.resultado == ResultadoPago.SALDO_DEUDA and pago.comision == deuda.monto * Decimal("0.10")
    assert deuda.estado == EstadoDeuda.PAGADA and deuda.transaccion_id == "77"
    assert r.estado == EstadoReserva.FINALIZADA


def test_webhook_con_monto_distinto_no_salda(cliente, playero, garaje, vehiculo, mp):  # noqa: F811
    conectar(garaje)
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
    escanear(cliente(playero), EGRESO, garaje, r)
    deuda = Deuda.objects.get(reserva=r)
    _pago_deuda(mp, 78, deuda, monto=1)
    assert procesar_notificacion_pago(78, "555").resultado == ResultadoPago.MONTO_INCORRECTO
    deuda.refresh_from_db()
    assert deuda.estado == EstadoDeuda.PENDIENTE


def test_pago_mp_de_deuda_ya_cobrada_en_efectivo_se_reembolsa(cliente, playero, garaje, vehiculo, mp):  # noqa: F811
    conectar(garaje)
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
    c = cliente(playero)
    escanear(c, EGRESO, garaje, r)
    c.post(f"/api/operacion/deudas/{r.id}/efectivo/")
    _pago_deuda(mp, 79, Deuda.objects.get(reserva=r))
    assert procesar_notificacion_pago(79, "555").resultado == ResultadoPago.REEMBOLSADO
    assert mp.reembolsos == ["79"]


# ---------- CU-09: el conductor salda su deuda ----------

MIS_DEUDAS = "/api/operacion/mis-deudas/"


def con_deuda(garaje, vehiculo):
    r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.CON_DEUDA)
    Deuda.objects.create(
        reserva=r, patente=vehiculo.patente, egreso_real=en(0), minutos_excedidos=30, tolerancia_min=10,
        fraccion_min=15, fracciones=2, precio_fraccion=1000, recargo=Decimal("0.50"), monto=3000,
    )
    return r


def test_cu09_el_conductor_ve_sus_deudas_pendientes(cliente, conductor, crear_usuario, garaje, vehiculo):
    r = con_deuda(garaje, vehiculo)
    datos = cliente(conductor).get(MIS_DEUDAS).data
    assert [d["reserva_id"] for d in datos] == [r.id]
    assert (datos[0]["garaje_nombre"], datos[0]["total"]) == (garaje.nombre, Decimal("3000.00"))
    assert cliente(crear_usuario("otro@test.com")).get(MIS_DEUDAS).data == []


def test_cu09_pagar_desde_la_app_vuelve_por_deep_link(cliente, conductor, garaje, vehiculo, mp):  # noqa: F811
    conectar(garaje)
    r = con_deuda(garaje, vehiculo)
    res = cliente(conductor).post(f"{MIS_DEUDAS}{r.id}/pagar/", {"canal": "app"}, format="json")
    assert res.status_code == 200 and res.data["init_point"] == "https://mp/checkout"
    preferencia = mp.preferencias[-1]
    assert preferencia["external_reference"] == f"deuda:{r.id}" and preferencia["auto_return"] == "approved"
    assert preferencia["back_urls"]["success"].startswith("drivly://pago-resultado")

    _pago_deuda(mp, 80, Deuda.objects.get(reserva=r))
    assert procesar_notificacion_pago(80, "555").resultado == ResultadoPago.SALDO_DEUDA
    assert cliente(conductor).get(MIS_DEUDAS).data == [] and not reservas.tiene_deuda(conductor)


def test_cu09_pagos_simulados_saldan_directo(cliente, conductor, garaje, vehiculo, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    r = con_deuda(garaje, vehiculo)
    assert cliente(conductor).post(f"{MIS_DEUDAS}{r.id}/pagar/", format="json").data == {"estado": "PAGADA"}
    assert Deuda.objects.get(reserva=r).medio == MedioCobro.MERCADO_PAGO and not reservas.tiene_deuda(conductor)


def test_cu09_no_se_paga_una_deuda_ajena_ni_una_saldada(cliente, conductor, crear_usuario, garaje, vehiculo):
    r = con_deuda(garaje, vehiculo)
    url = f"{MIS_DEUDAS}{r.id}/pagar/"
    assert cliente(crear_usuario("otro@test.com")).post(url, format="json").status_code == 404
    Deuda.objects.update(estado=EstadoDeuda.PAGADA)
    assert cliente(conductor).post(url, format="json").status_code == 404


def test_cu09_garaje_sin_mercado_pago_no_ofrece_otro_garaje(cliente, conductor, garaje, vehiculo, mp):  # noqa: F811
    r = con_deuda(garaje, vehiculo)
    res = cliente(conductor).post(f"{MIS_DEUDAS}{r.id}/pagar/", {"canal": "app"}, format="json")
    assert res.status_code == 409 and "en persona" in res.data["detail"]


def test_abono_entra_y_sale_varias_veces(cliente, playero, garaje, vehiculo):
    r = crear_reserva(garaje, vehiculo, en(-60), en(60 * 24 * 20), modalidad=Modalidad.MENSUAL)
    c = cliente(playero)
    for _ in range(2):
        assert escanear(c, INGRESO, garaje, r).data["reserva"]["estado"] == "EN_CURSO"
        assert escanear(c, EGRESO, garaje, r).data["reserva"]["estado"] == "CONFIRMADA"
    assert Movimiento.objects.filter(reserva=r).count() == 4


def test_abono_vencido_paga_overstay_con_tarifa_por_hora(cliente, playero, garaje, vehiculo, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    with freeze_time(AHORA):
        r = crear_reserva(garaje, vehiculo, en(-9000), en(-40), EstadoReserva.EN_CURSO, Modalidad.MENSUAL)
        assert escanear(cliente(playero), EGRESO, garaje, r).data["deuda"]["fracciones"] == 2


def test_cp31_abono_suspendido_por_deuda(cliente, playero, garaje, vehiculo):
    crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.CON_DEUDA)
    abono = crear_reserva(garaje, vehiculo, en(-60), en(9000), modalidad=Modalidad.MENSUAL)
    res = escanear(cliente(playero), INGRESO, garaje, abono)
    assert res.status_code == 402 and res.data["code"] == "DEUDA_PENDIENTE"


def _presencial(c, garaje, patente="AC908KL", minutos=60):
    return c.post(INGRESO, {"garaje": str(garaje.id), "patente": patente, "salida_estimada": en(minutos).isoformat()},
                  format="json")


def test_presencial_paga_lo_que_estuvo(cliente, playero, garaje):
    c = cliente(playero)
    with freeze_time(AHORA) as reloj:
        res = _presencial(c, garaje, "ac 908 kl")
        assert res.status_code == 200
        assert res.data["reserva"]["origen"] == "PRESENCIAL" and res.data["reserva"]["patente"] == "AC908KL"
        assert res.data["ocupacion"]["ocupados_presencial"] == 1
        assert _presencial(c, garaje).status_code == 409  # la misma patente no entra dos veces
        reloj.tick(timedelta(minutes=46))
        egreso = c.post(EGRESO, {"garaje": str(garaje.id), "patente": "AC908KL"}, format="json")
    assert egreso.data["reserva"]["estado"] == "FINALIZADA"
    assert egreso.data["reserva"]["total"] == "4000.00" and egreso.data["deuda"] is None  # 4 fracciones


def test_presencial_exige_salida_estimada_futura(cliente, playero, garaje):
    c = cliente(playero)
    assert c.post(INGRESO, {"garaje": str(garaje.id), "patente": "AC908KL"}, format="json").status_code == 400
    assert _presencial(c, garaje, minutos=-5).status_code == 400


def test_patente_invalida_se_rechaza(cliente, playero, garaje):
    assert _presencial(cliente(playero), garaje, "NOVALE").status_code == 400


def test_cp26_semaforo_en_rojo_no_registra_y_deriva(cliente, playero, garaje, vehiculo, admin_garaje, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    cerca = Garaje.objects.create(admin=admin_garaje, nombre="Cerca", cuit=garaje.cuit, direccion="y",
                                  lat=garaje.lat, lng=garaje.lng, capacidad=5)
    Tarifa.objects.create(garaje=cerca, categoria="AUTO", modalidad="HORA", precio_fraccion=900, fraccion_min=15,
                          minimo_fracciones=1)
    crear_reserva(garaje, vehiculo, en(30), en(90))
    res = _presencial(cliente(playero), garaje, minutos=60)
    assert res.status_code == 409 and res.data["code"] == "SIN_LUGAR_PRESENCIAL"
    assert [g["nombre"] for g in res.data["cercanos"]] == ["Cerca"]
    assert not Reserva.objects.filter(modalidad=Modalidad.PRESENCIAL).exists()


def test_cp27_sin_lugar_reembolsa_y_registra_incidente(cliente, playero, garaje, vehiculo, mp):  # noqa: F811
    conectar(garaje)
    r = crear_reserva(garaje, vehiculo, en(-5), en(60))
    Pago.objects.create(reserva=r, payment_id="50", estado_mp="approved", monto=4000,
                        resultado=ResultadoPago.CONFIRMO_RESERVA)
    res = escanear(cliente(playero), SIN_LUGAR, garaje, r)
    assert res.status_code == 200 and res.data["reserva"]["estado"] == "SIN_LUGAR"
    assert res.data["reembolso"] == {"monto": Decimal("4000.00"), "estado": ResultadoPago.REEMBOLSADO}
    assert mp.reembolsos == ["50"]
    assert Incidente.objects.filter(garaje=garaje, reserva=r, registrado_por=playero).exists()


def test_sin_lugar_sin_pago_registrado(cliente, playero, garaje, vehiculo):
    r = crear_reserva(garaje, vehiculo, en(-5), en(60))
    assert escanear(cliente(playero), SIN_LUGAR, garaje, r).data["reembolso"]["estado"] == "SIN_PAGO"


def test_metricas_del_dia(cliente, admin_garaje, playero, garaje, vehiculo, settings):
    settings.DRIVLY_PAGOS_SIMULADOS = True
    with freeze_time(AHORA) as reloj:
        c = cliente(playero)
        r = crear_reserva(garaje, vehiculo, en(-100), en(-40), EstadoReserva.EN_CURSO)
        Reserva.objects.filter(pk=r.pk).update(confirmada_en=timezone.now())
        escanear(c, EGRESO, garaje, r)
        c.post(f"/api/operacion/deudas/{r.id}/efectivo/")
        _presencial(c, garaje)
        reloj.tick(timedelta(minutes=30))
        c.post(EGRESO, {"garaje": str(garaje.id), "patente": "AC908KL"}, format="json")
        m = cliente(admin_garaje).get(f"/api/garajes/{garaje.id}/metricas/").data
    assert (m["recaudacion_app"], m["recaudacion_presencial"], m["recaudacion_excedentes"]) == (4000, 2000, 3000)
    assert m["recaudacion_total"] == 9000 and m["reservas_confirmadas"] == 1 and m["reservas_variacion"] == 1
    assert m["ocupacion_pico_lugares"] == 1 and m["ocupacion_pico"] == 1 / garaje.capacidad


def test_metricas_sin_datos_y_permisos(cliente, admin_garaje, playero, garaje):
    url = f"/api/garajes/{garaje.id}/metricas/"
    m = cliente(admin_garaje).get(url, {"fecha": "2026-01-15"}).data
    assert m["ocupacion_pico"] == 0 and m["recaudacion_total"] == 0
    assert cliente(admin_garaje).get(url, {"fecha": "ayer"}).status_code == 400
    assert cliente(playero).get(url).status_code == 403
