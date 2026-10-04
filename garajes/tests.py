from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from cuentas.models import Rol, Usuario
from garajes.models import Garaje, Modalidad, Tarifa, validar_cuit
from vehiculos.models import Categoria

INICIO = datetime(2026, 10, 5, 14, 0)


def test_cuit_valido_e_invalido():
    validar_cuit("20-12345678-6")
    validar_cuit("30712345671")
    with pytest.raises(ValidationError):
        validar_cuit("20-12345678-5")


@pytest.mark.parametrize("minutos, esperado", [(80, 6000), (15, 1000), (10, 2000), (121, 9000)])
def test_cotizar_por_fraccion(garaje, minutos, esperado):
    t = Tarifa.objects.create(garaje=garaje, categoria=Categoria.AUTO, precio_fraccion=Decimal("1000"),
                              fraccion_min=15, minimo_fracciones=2 if minutos == 10 else 1)
    assert t.cotizar(INICIO, INICIO + timedelta(minutes=minutos)) == Decimal(esperado)


def test_cotizar_abono_es_precio_fijo(garaje):
    t = Tarifa.objects.create(garaje=garaje, categoria=Categoria.AUTO, modalidad=Modalidad.MENSUAL,
                              precio_periodo=Decimal("150000"))
    assert t.cotizar(INICIO, INICIO + timedelta(days=30)) == Decimal("150000")


def test_db_impide_tarifa_hora_sin_fraccion(garaje):
    with pytest.raises(IntegrityError):
        Tarifa.objects.create(garaje=garaje, categoria=Categoria.AUTO, precio_periodo=Decimal("100"))


def test_db_impide_cupo_abonos_mayor_a_capacidad(garaje):
    garaje.cupo_abonos = 51
    with pytest.raises(IntegrityError):
        garaje.save()


def test_admin_crea_garaje_y_valida_reglas(admin_garaje, cliente):
    datos = {"nombre": "Centro", "cuit": "30-71234567-1", "direccion": "Florida 100",
             "lat": "-34.603", "lng": "-58.375", "capacidad": 20, "cupo_abonos": 5}
    r = cliente(admin_garaje).post("/api/garajes/", datos, format="json")
    assert r.status_code == 201
    assert Garaje.objects.get(id=r.data["id"]).admin == admin_garaje
    r = cliente(admin_garaje).post("/api/garajes/", {**datos, "cupo_abonos": 30}, format="json")
    assert r.status_code == 400 and "cupo_abonos" in r.data
    r = cliente(admin_garaje).post("/api/garajes/", {**datos, "cuit": "20-12345678-5"}, format="json")
    assert r.status_code == 400 and "cuit" in r.data


def test_conductor_no_crea_y_no_ve_cuit(conductor, garaje, cliente):
    assert cliente(conductor).post("/api/garajes/", {}, format="json").status_code == 403
    r = cliente(conductor).get(f"/api/garajes/{garaje.id}/")
    assert r.status_code == 200 and "cuit" not in r.data


def test_admin_no_ve_garaje_ajeno(otro_admin, garaje, cliente):
    assert cliente(otro_admin).get(f"/api/garajes/{garaje.id}/").status_code == 404


def test_busqueda_por_cercania(conductor, admin_garaje, garaje, cliente):
    Garaje.objects.create(admin=admin_garaje, nombre="Lejos", cuit="30-71234567-1", direccion="Belgrano",
                          lat=Decimal("-34.562"), lng=Decimal("-58.456"), capacidad=10)  # ~3,8 km
    r = cliente(conductor).get("/api/garajes/", {"lat": "-34.5885", "lng": "-58.4305", "radio": 1000})
    assert [g["nombre"] for g in r.data] == ["Garaje Palermo"]
    assert r.data[0]["distancia_m"] < 100


def test_desactivar_oculta_al_conductor(admin_garaje, conductor, garaje, cliente):
    assert cliente(admin_garaje).delete(f"/api/garajes/{garaje.id}/").status_code == 204
    garaje.refresh_from_db()
    assert garaje.activo is False
    assert cliente(conductor).get(f"/api/garajes/{garaje.id}/").status_code == 404


def test_tarifa_api(admin_garaje, otro_admin, garaje, cliente):
    hora = {"garaje": str(garaje.id), "categoria": "AUTO", "modalidad": "HORA",
            "precio_fraccion": "1000", "fraccion_min": 15, "minimo_fracciones": 1}
    assert cliente(admin_garaje).post("/api/tarifas/", hora, format="json").status_code == 201
    # duplicada
    assert cliente(admin_garaje).post("/api/tarifas/", hora, format="json").status_code == 400
    # abono sin precio_periodo
    r = cliente(admin_garaje).post("/api/tarifas/", {"garaje": str(garaje.id), "categoria": "AUTO",
                                                     "modalidad": "MENSUAL"}, format="json")
    assert r.status_code == 400 and "precio_periodo" in r.data
    # garaje ajeno
    r = cliente(otro_admin).post("/api/tarifas/", {**hora, "categoria": "MOTO"}, format="json")
    assert r.status_code == 400


def test_alta_y_baja_de_playero(admin_garaje, garaje, cliente, conductor):
    c = cliente(admin_garaje)
    r = c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": "Pepe@Test.com", "nombre": "Pepe"}, format="json")
    assert r.status_code == 201
    playero = Usuario.objects.get(email="pepe@test.com")
    assert playero.rol == Rol.PLAYERO and playero.garaje == garaje
    # el playero sólo ve su garaje
    assert [g["id"] for g in cliente(playero).get("/api/garajes/").data["results"]] == [str(garaje.id)]
    # no se puede usar el email de un conductor
    r = c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": conductor.email}, format="json")
    assert r.status_code == 400
    # baja
    assert c.delete(f"/api/garajes/{garaje.id}/playeros/{playero.id}/").status_code == 204
    playero.refresh_from_db()
    assert playero.garaje is None and playero.is_active is False
