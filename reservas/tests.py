"""
Casos de prueba de la documentación (sección 15). Corren contra PostgreSQL: tstzrange,
GiST y SELECT ... FOR UPDATE no existen en SQLite.
Escenario base: garaje con capacidad 2, auto $1.000 por fracción de 15 min.
"""
import threading
import time
from datetime import timedelta
from decimal import Decimal
from itertools import count

import pytest
from django.db import connection
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone
from freezegun import freeze_time

from cuentas.models import Rol, Usuario
from garajes.models import Garaje, Tarifa
from reservas import services
from reservas.exceptions import SinCupo
from reservas.models import EstadoReserva, Modalidad, Reserva
from reservas.periodos import sumar_meses
from vehiculos.models import Vehiculo

_seq = count(100)


def manana(h, m=0):
    """Mañana a las h:m hora de Argentina (siempre en el futuro)."""
    base = timezone.localtime() + timedelta(days=1)
    return base.replace(hour=h, minute=m, second=0, microsecond=0)


def nuevo_conductor():
    n = next(_seq)
    u = Usuario.objects.create_user(email=f"c{n}@test.com", rol=Rol.CONDUCTOR)
    v = Vehiculo.objects.create(conductor=u, patente=f"AA{n:03d}BB", categoria="AUTO",
                                categoria_origen="DATACAR", estado_validacion="VALIDADO")
    return u, v


@pytest.fixture
def garaje(admin_garaje):
    g = Garaje.objects.create(admin=admin_garaje, nombre="Palermo", cuit="30-71234567-1", direccion="Gorriti 4800",
                              lat=Decimal("-34.588"), lng=Decimal("-58.430"), capacidad=2, cupo_abonos=1)
    Tarifa.objects.create(garaje=g, categoria="AUTO", precio_fraccion=Decimal("1000"), fraccion_min=15, minimo_fracciones=1)
    Tarifa.objects.create(garaje=g, categoria="AUTO", modalidad="MENSUAL", precio_periodo=Decimal("150000"))
    return g


@pytest.fixture
def conductor_v(db):
    return nuevo_conductor()


def ocupar(garaje, ini, fin, estado=EstadoReserva.CONFIRMADA, modalidad=Modalidad.HORA, **extra):
    """Crea una reserva directamente en la base, para armar escenarios."""
    if modalidad == Modalidad.PRESENCIAL:
        return Reserva.objects.create(garaje=garaje, modalidad=modalidad, periodo=DateTimeTZRange(ini, fin),
                                      estado=estado, patente_presencial="AC908KL", salida_estimada=fin, **extra)
    u, v = nuevo_conductor()
    if estado == EstadoReserva.HOLD:
        extra.setdefault("hold_expira", timezone.now() + timedelta(minutes=5))
    return Reserva.objects.create(conductor=u, vehiculo=v, garaje=garaje, modalidad=modalidad,
                                  periodo=DateTimeTZRange(ini, fin), estado=estado, **extra)


def pedir(cliente, conductor_v, garaje, ini, fin=None, modalidad="HORA"):
    u, v = conductor_v
    body = {"garaje": str(garaje.id), "vehiculo": str(v.id), "modalidad": modalidad, "inicio": ini.isoformat()}
    if fin:
        body["fin"] = fin.isoformat()
    return cliente(u).post("/api/reservas/hold/", body, format="json")


# ---------- Regla 1: capacidad ----------

def test_cp01_hold_con_cupo(cliente, conductor_v, garaje):
    r = pedir(cliente, conductor_v, garaje, manana(14), manana(16))
    assert r.status_code == 201, r.data
    assert r.data["estado"] == "HOLD" and r.data["categoria"] == "AUTO"
    assert r.data["desglose"]["fracciones"] == 8 and Decimal(r.data["total"]) == Decimal("8000")
    vence = Reserva.objects.get(id=r.data["id"]).hold_expira - timezone.now()
    assert timedelta(minutes=4, seconds=55) < vence <= timedelta(minutes=5)


def test_cp02_capacidad_llena_ofrece_cercanos(cliente, conductor_v, garaje, admin_garaje):
    ocupar(garaje, manana(14), manana(16))
    ocupar(garaje, manana(14), manana(16))
    vecino = Garaje.objects.create(admin=admin_garaje, nombre="Vecino", cuit="30-71234567-1", direccion="Thames 1580",
                                   lat=Decimal("-34.5878"), lng=Decimal("-58.4334"), capacidad=5)
    Tarifa.objects.create(garaje=vecino, categoria="AUTO", precio_fraccion=Decimal("900"), fraccion_min=15, minimo_fracciones=1)
    r = pedir(cliente, conductor_v, garaje, manana(15), manana(15, 30))
    assert r.status_code == 409 and r.data["code"] == "SIN_CUPO"
    assert [g["nombre"] for g in r.data["cercanos"]] == ["Vecino"] and r.data["cercanos"][0]["lugares_libres"] == 5


def test_cp03_solapadas_que_no_coexisten_con_capacidad_1(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    ocupar(garaje, manana(13), manana(14))
    ocupar(garaje, manana(15), manana(16))
    assert pedir(cliente, conductor_v, garaje, manana(13), manana(16)).status_code == 409


def test_cp04_pico_real_menor_al_conteo(cliente, conductor_v, garaje):
    """Hay 2 reservas solapadas con el pedido, pero nunca coexisten: el pico es 1 < 2."""
    ocupar(garaje, manana(13), manana(14))
    ocupar(garaje, manana(15), manana(16))
    assert pedir(cliente, conductor_v, garaje, manana(13), manana(16)).status_code == 201


def test_cp05_limite_semiabierto(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    ocupar(garaje, manana(14), manana(16))
    assert pedir(cliente, conductor_v, garaje, manana(16), manana(17)).status_code == 201


@pytest.mark.django_db(transaction=True)
def test_cp06_concurrencia_veinte_pedidos_un_lugar(admin_garaje, monkeypatch):
    """
    20 hilos piden el último lugar al mismo tiempo: entra exactamente uno.
    La demora entre leer los lugares libres y crear la reserva agranda la ventana de carrera:
    sin el SELECT ... FOR UPDATE sobre el garaje, varios hilos leen "1 libre" y entran todos.
    """
    original = services.lugares_libres

    def lento(*args, **kwargs):
        libres = original(*args, **kwargs)
        time.sleep(0.05)
        return libres

    monkeypatch.setattr(services, "lugares_libres", lento)
    garaje = Garaje.objects.create(admin=admin_garaje, nombre="Concurrencia", cuit="30-71234567-1", direccion="x",
                                   lat=Decimal("-34.6"), lng=Decimal("-58.4"), capacidad=1)
    Tarifa.objects.create(garaje=garaje, categoria="AUTO", precio_fraccion=Decimal("1000"), fraccion_min=15, minimo_fracciones=1)
    conductores = [nuevo_conductor() for _ in range(20)]
    barrera = threading.Barrier(20)
    resultados = []

    def intentar(u, v):
        try:
            barrera.wait()
            services.crear_hold(u, garaje.id, v.id, Modalidad.HORA, manana(14), manana(15))
            resultados.append("ok")
        except SinCupo:
            resultados.append("sin_cupo")
        except Exception as e:  # cualquier otro error haría fallar el test con el detalle
            resultados.append(repr(e))
        finally:
            connection.close()

    hilos = [threading.Thread(target=intentar, args=c) for c in conductores]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sorted(resultados) == ["ok"] + ["sin_cupo"] * 19
    assert Reserva.objects.filter(garaje=garaje, estado="HOLD").count() == 1


# ---------- Regla 2: hold de 5 minutos ----------

def test_cp07_hold_vencido_libera_sin_correr_la_tarea(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    assert pedir(cliente, nuevo_conductor(), garaje, manana(14), manana(15)).status_code == 201
    with freeze_time(timezone.now() + timedelta(minutes=5, seconds=1)):
        assert pedir(cliente, conductor_v, garaje, manana(14), manana(15)).status_code == 201


def test_cp08_hold_vigente_bloquea(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    pedir(cliente, nuevo_conductor(), garaje, manana(14), manana(15))
    with freeze_time(timezone.now() + timedelta(minutes=4)):
        assert pedir(cliente, conductor_v, garaje, manana(14), manana(15)).status_code == 409


def test_cp09_tarea_de_expiracion(garaje):
    r = ocupar(garaje, manana(14), manana(15), estado=EstadoReserva.HOLD, hold_expira=timezone.now() - timedelta(seconds=1))
    vigente = ocupar(garaje, manana(14), manana(15), estado=EstadoReserva.HOLD)
    from reservas.tasks import expirar_holds
    assert expirar_holds() == 1
    r.refresh_from_db(); vigente.refresh_from_db()
    assert r.estado == "EXPIRADA" and vigente.estado == "HOLD"


def test_cp10_pago_dentro_del_ttl_confirma_y_emite_qr(cliente, conductor_v, garaje, settings):
    """Con pagos simulados. El flujo real con Mercado Pago se prueba en pagos/tests.py."""
    settings.DRIVLY_PAGOS_SIMULADOS = True
    u, _ = conductor_v
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    r = cliente(u).post(f"/api/reservas/{rid}/pagar/")
    assert r.status_code == 200 and r.data["estado"] == "CONFIRMADA"
    qr = cliente(u).get(f"/api/reservas/{rid}/qr/").data
    assert qr["qr_token"].startswith("drivly.v1.") and qr["reutilizable"] is False
    assert str(services.reserva_desde_qr(qr["qr_token"]).id) == rid


def test_qr_adulterado_se_rechaza(garaje):
    r = ocupar(garaje, manana(14), manana(15))
    token = services.generar_qr_token(r)
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):
        services.reserva_desde_qr(token[:-2] + "xx")
    otra = ocupar(garaje, manana(16), manana(17))
    with pytest.raises(ValidationError):  # firma de una reserva pegada a otra
        services.reserva_desde_qr(f"drivly.v1.{otra.id}.{token.rsplit('.', 1)[1]}")


def test_cp11_pago_tardio_con_cupo_confirma(cliente, conductor_v, garaje):
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    with freeze_time(timezone.now() + timedelta(minutes=7)):
        assert services.confirmar_pago(rid).estado == "CONFIRMADA"


def test_cp12_pago_tardio_sin_cupo(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    with freeze_time(timezone.now() + timedelta(minutes=6)):
        assert pedir(cliente, nuevo_conductor(), garaje, manana(14), manana(15)).status_code == 201
    with freeze_time(timezone.now() + timedelta(minutes=7)):
        from reservas.exceptions import HoldVencidoSinCupo
        with pytest.raises(HoldVencidoSinCupo):
            services.confirmar_pago(rid)
    assert Reserva.objects.get(id=rid).estado == "EXPIRADA"


def test_cp13_confirmar_dos_veces_es_idempotente(cliente, conductor_v, garaje):
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    primero = services.confirmar_pago(rid).qr_token
    assert services.confirmar_pago(rid).qr_token == primero


def test_cancelar_hold_libera_el_lugar(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    u, _ = conductor_v
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    assert cliente(u).post(f"/api/reservas/{rid}/cancelar/").data["estado"] == "CANCELADA"
    assert pedir(cliente, nuevo_conductor(), garaje, manana(14), manana(15)).status_code == 201


def test_cancelar_confirmada_con_pagos_simulados_no_reembolsa(cliente, conductor_v, garaje):
    u, v = conductor_v
    r = ocupar(garaje, manana(14), manana(15))
    Reserva.objects.filter(id=r.id).update(conductor=u, vehiculo=v)
    datos = cliente(u).get(f"/api/reservas/{r.id}/").data
    assert datos["cancelable_hasta"] is not None
    respuesta = cliente(u).post(f"/api/reservas/{r.id}/cancelar/").data
    assert respuesta["estado"] == "CANCELADA" and respuesta["reembolso"] is None and respuesta["cancelable_hasta"] is None


def test_no_se_cancela_una_reserva_en_curso(cliente, conductor_v, garaje):
    u, v = conductor_v
    r = Reserva.objects.create(conductor=u, vehiculo=v, garaje=garaje, periodo=DateTimeTZRange(manana(14), manana(15)),
                               estado=EstadoReserva.EN_CURSO)
    assert cliente(u).post(f"/api/reservas/{r.id}/cancelar/").status_code == 409


# ---------- Reglas 3 y 4 ----------

def test_cp19_overstay_activo_sigue_ocupando(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    ahora = timezone.now()
    ocupar(garaje, ahora - timedelta(hours=2), ahora - timedelta(minutes=30), estado=EstadoReserva.EN_CURSO)
    r = pedir(cliente, conductor_v, garaje, ahora + timedelta(minutes=15), ahora + timedelta(hours=1))
    assert r.status_code == 409


def test_cp20_deuda_bloquea_reservas(cliente, conductor_v, garaje):
    u, v = conductor_v
    Reserva.objects.create(conductor=u, vehiculo=v, garaje=garaje, estado=EstadoReserva.CON_DEUDA,
                           periodo=DateTimeTZRange(timezone.now() - timedelta(hours=3), timezone.now() - timedelta(hours=1)))
    r = pedir(cliente, conductor_v, garaje, manana(14), manana(15))
    assert r.status_code == 402 and r.data["code"] == "DEUDA_PENDIENTE"


def test_cp22_cambio_de_tarifa_no_altera_reservas(cliente, conductor_v, garaje):
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    Tarifa.objects.filter(garaje=garaje, modalidad="HORA").update(precio_fraccion=Decimal("5000"))
    assert Reserva.objects.get(id=rid).monto == Decimal("4000")


def test_vehiculo_sin_categoria_no_reserva(cliente, garaje):
    u, v = nuevo_conductor()
    Vehiculo.objects.filter(id=v.id).update(categoria=None, categoria_origen=None, estado_validacion="PENDIENTE")
    r = pedir(cliente, (u, v), garaje, manana(14), manana(15))
    assert r.status_code == 422 and r.data["code"] == "VEHICULO_SIN_CATEGORIA"


def test_sin_tarifa_para_la_categoria(cliente, garaje):
    u, v = nuevo_conductor()
    Vehiculo.objects.filter(id=v.id).update(categoria="CAMIONETA")
    r = pedir(cliente, (u, v), garaje, manana(14), manana(15))
    assert r.status_code == 409 and r.data["code"] == "SIN_TARIFA"


def test_mismo_vehiculo_no_reserva_dos_veces_a_la_vez(cliente, conductor_v, garaje):
    pedir(cliente, conductor_v, garaje, manana(14), manana(16))
    r = pedir(cliente, conductor_v, garaje, manana(15), manana(17))
    assert r.status_code == 409 and r.data["code"] == "VEHICULO_OCUPADO"


@pytest.mark.parametrize("ini, fin, campo", [
    (lambda: timezone.now() - timedelta(hours=1), lambda: timezone.now() + timedelta(hours=1), "inicio"),
    (lambda: manana(14), lambda: manana(14), "fin"),
    (lambda: manana(8), lambda: manana(8) + timedelta(hours=25), "fin"),
    (lambda: manana(14), lambda: None, "fin"),
])
def test_intervalos_invalidos(cliente, conductor_v, garaje, ini, fin, campo):
    r = pedir(cliente, conductor_v, garaje, ini(), fin())
    assert r.status_code == 400 and campo in r.data


# ---------- Regla 5: abonos ----------

def test_sumar_meses_ajusta_fin_de_mes():
    base = timezone.localtime().replace(year=2027, month=1, day=31)
    assert sumar_meses(base, 1).day == 28 and sumar_meses(base, 1).month == 2
    assert sumar_meses(base, 12).year == 2028


def test_hold_de_abono_mensual(cliente, conductor_v, garaje):
    r = pedir(cliente, conductor_v, garaje, manana(9), modalidad="MENSUAL")
    assert r.status_code == 201, r.data
    reserva = Reserva.objects.get(id=r.data["id"])
    assert reserva.fin == sumar_meses(reserva.inicio, 1) and reserva.monto == Decimal("150000")


def test_cp23_abono_ocupa_capacidad(cliente, conductor_v, garaje):
    garaje.capacidad = 1
    garaje.save()
    ocupar(garaje, manana(0), sumar_meses(manana(0), 1), modalidad=Modalidad.MENSUAL)
    assert pedir(cliente, conductor_v, garaje, manana(14), manana(15)).status_code == 409


def test_cp24_cupo_de_abonos(cliente, garaje):
    """Capacidad 2, cupo de abonos 1, un abono activo: otro abono no entra, una reserva por hora sí."""
    ocupar(garaje, manana(0), sumar_meses(manana(0), 1), modalidad=Modalidad.MENSUAL)
    r = pedir(cliente, nuevo_conductor(), garaje, manana(9), modalidad="MENSUAL")
    assert r.status_code == 409 and r.data["code"] == "SIN_CUPO"
    assert pedir(cliente, nuevo_conductor(), garaje, manana(14), manana(15)).status_code == 201


# ---------- Regla 6: presenciales y garajes cercanos ----------

def test_cp25_presencial_cuenta_en_la_ocupacion(cliente, conductor_v, garaje):
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    ahora = timezone.now()
    ocupar(garaje, ahora - timedelta(minutes=10), ahora + timedelta(hours=2), estado=EstadoReserva.EN_CURSO,
           modalidad=Modalidad.PRESENCIAL)
    r = pedir(cliente, conductor_v, garaje, ahora + timedelta(hours=1), ahora + timedelta(hours=3))
    assert r.status_code == 409 and "cercanos" in r.data


def test_cp26_semaforo_descuenta_reservas_que_llegan(cliente, garaje, admin_garaje):
    """Capacidad 1, una reserva de la app llega en 30 min: hay 1 libre ahora, pero 0 para presenciales."""
    garaje.capacidad, garaje.cupo_abonos = 1, 0
    garaje.save()
    ahora = timezone.now()
    ocupar(garaje, ahora + timedelta(minutes=30), ahora + timedelta(minutes=90))
    o = cliente(admin_garaje).get(f"/api/garajes/{garaje.id}/ocupacion/").data
    assert o["libres"] == 1 and o["proximas_app"] == 1 and o["libres_presencial"] == 0
    assert len(o["franjas"]) == 18


def test_ocupacion_separa_app_abonos_y_presenciales(cliente, garaje, admin_garaje):
    garaje.capacidad = 10
    garaje.save()
    ahora = timezone.now()
    ocupar(garaje, ahora - timedelta(hours=1), ahora + timedelta(hours=1), estado=EstadoReserva.EN_CURSO)
    ocupar(garaje, ahora - timedelta(days=1), sumar_meses(ahora, 1), modalidad=Modalidad.MENSUAL)
    ocupar(garaje, ahora - timedelta(minutes=5), ahora + timedelta(hours=2), estado=EstadoReserva.EN_CURSO,
           modalidad=Modalidad.PRESENCIAL)
    o = cliente(admin_garaje).get(f"/api/garajes/{garaje.id}/ocupacion/").data
    assert (o["ocupados_app"], o["ocupados_abonos"], o["ocupados_presencial"], o["libres"]) == (1, 1, 1, 7)


def test_conductor_no_ve_ocupacion(cliente, conductor_v, garaje):
    assert cliente(conductor_v[0]).get(f"/api/garajes/{garaje.id}/ocupacion/").status_code == 403


def test_disponibles_y_cercanos(cliente, conductor_v, garaje, admin_garaje):
    vecino = Garaje.objects.create(admin=admin_garaje, nombre="Vecino", cuit="30-71234567-1", direccion="Thames 1580",
                                   lat=Decimal("-34.5878"), lng=Decimal("-58.4334"), capacidad=5)
    Tarifa.objects.create(garaje=vecino, categoria="AUTO", precio_fraccion=Decimal("900"), fraccion_min=15, minimo_fracciones=1)
    ocupar(garaje, manana(14), manana(16))
    ocupar(garaje, manana(14), manana(16))
    c = cliente(conductor_v[0])
    q = {"lat": "-34.5885", "lng": "-58.4305", "inicio": manana(14).isoformat(), "fin": manana(15).isoformat()}
    r = c.get("/api/garajes/disponibles/", q).data
    assert {g["nombre"]: g["lugares_libres"] for g in r} == {"Palermo": 0, "Vecino": 5}
    assert r[0]["nombre"] == "Palermo" and r[0]["precio_unidad"] == "/ 15 min"
    # Sólo Palermo ofrece mensual
    r = c.get("/api/garajes/disponibles/", {**q, "modalidad": "MENSUAL"}).data
    assert [g["nombre"] for g in r] == ["Palermo"] and Decimal(r[0]["precio_desde"]) == Decimal("150000")
    # Cercanos a Palermo: sólo los que tienen lugar, sin incluirse
    r = c.get(f"/api/garajes/{garaje.id}/cercanos/", q).data
    assert [g["nombre"] for g in r] == ["Vecino"]


# ---------- Permisos ----------

def test_cada_rol_ve_sus_reservas(cliente, conductor_v, garaje, otro_admin):
    pedir(cliente, conductor_v, garaje, manana(14), manana(15))
    otro = nuevo_conductor()
    assert cliente(conductor_v[0]).get("/api/reservas/").data["count"] == 1
    assert cliente(otro[0]).get("/api/reservas/").data["count"] == 0
    assert cliente(garaje.admin).get("/api/reservas/", {"estado": "HOLD"}).data["count"] == 1
    assert cliente(otro_admin).get("/api/reservas/").data["count"] == 0
    playero = Usuario.objects.create_user(email="p@test.com", rol=Rol.PLAYERO, garaje=garaje)
    assert cliente(playero).get("/api/reservas/").data["count"] == 1


def test_solo_conductores_crean_holds(cliente, garaje, conductor_v):
    u, v = conductor_v
    body = {"garaje": str(garaje.id), "vehiculo": str(v.id), "inicio": manana(14).isoformat(), "fin": manana(15).isoformat()}
    assert cliente(garaje.admin).post("/api/reservas/hold/", body, format="json").status_code == 403


def test_pagar_reserva_ajena(cliente, conductor_v, garaje):
    rid = pedir(cliente, conductor_v, garaje, manana(14), manana(15)).data["id"]
    assert cliente(nuevo_conductor()[0]).post(f"/api/reservas/{rid}/pagar/").status_code == 404
