import pathlib
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


def _tarifa_caba(garaje, **extra):
    """Como el garaje del playero entrevistado: $9.000 la hora, $750 cada 5 min, estadía 12 h $36.000, 24 h $45.000."""
    datos = {"precio_primera_hora": Decimal("9000"), "precio_fraccion": Decimal("750"), "fraccion_min": 5,
             "minimo_fracciones": 12, "tope_12h": Decimal("36000"), "tope_24h": Decimal("45000"), **extra}
    return Tarifa.objects.create(garaje=garaje, categoria=Categoria.AUTO, **datos)


@pytest.mark.parametrize("minutos, esperado", [
    (20, 9000),      # la primera hora se cobra completa
    (60, 9000),
    (65, 9750),      # 1 h + una fracción de 5 min
    (90, 13500),     # 1 h + 6 fracciones
    (180, 27000),    # 3 h todavía es menos que la estadía
    (240, 36000),    # 4 h = $36.000: llega al tope de 12 h
    (540, 36000),    # 9 h: sigue en $36.000 (sin tope serían $81.000)
    (720, 36000),
    (721, 45000),    # pasadas las 12 h rige la estadía de 24 h
    (1440, 45000),
])
def test_cotizar_con_primera_hora_y_estadia(garaje, minutos, esperado):
    t = _tarifa_caba(garaje)
    assert t.cotizar(INICIO, INICIO + timedelta(minutes=minutos)) == Decimal(esperado)
    assert t.precio_hora == Decimal("9000")


def test_cotizar_sin_estadia_no_tiene_tope(garaje):
    t = _tarifa_caba(garaje, tope_12h=None, tope_24h=None)
    assert t.cotizar(INICIO, INICIO + timedelta(hours=9)) == Decimal("81000")


@pytest.mark.parametrize("campos, error", [
    ({"tope_12h": Decimal("5000")}, "tope_12h"),                            # menos que la primera hora
    ({"tope_24h": Decimal("30000")}, "tope_24h"),                           # menos que la de 12 h
    ({"tope_12h": Decimal("0")}, "tope_12h"),
])
def test_estadias_incoherentes(garaje, campos, error):
    t = Tarifa(garaje=garaje, categoria=Categoria.AUTO, precio_primera_hora=Decimal("9000"),
               precio_fraccion=Decimal("750"), fraccion_min=5, minimo_fracciones=12,
               tope_12h=Decimal("36000"), tope_24h=Decimal("45000"))
    for campo, valor in campos.items():
        setattr(t, campo, valor)
    with pytest.raises(ValidationError) as e:
        t.full_clean()
    assert error in e.value.message_dict


def test_abono_no_lleva_estadia(garaje):
    t = Tarifa(garaje=garaje, categoria=Categoria.AUTO, modalidad=Modalidad.MENSUAL,
               precio_periodo=Decimal("220500"), tope_12h=Decimal("36000"))
    with pytest.raises(ValidationError):
        t.full_clean()


def test_cotizacion_de_la_app_muestra_la_estadia(garaje, cliente, crear_usuario):
    from vehiculos.models import Vehiculo

    _tarifa_caba(garaje)
    u = crear_usuario("estadia@test.com")
    v = Vehiculo.objects.create(conductor=u, patente="AB123CD", categoria="AUTO",
                                categoria_origen="DATACAR", estado_validacion="VALIDADO")
    inicio = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0).astimezone()
    r = cliente(u).get("/api/reservas/cotizar/", {
        "garaje": str(garaje.id), "vehiculo": str(v.id), "modalidad": "HORA",
        "inicio": inicio.isoformat(), "fin": (inicio + timedelta(hours=9)).isoformat(),
    })
    assert r.status_code == 200, r.data
    assert Decimal(r.data["total"]) == Decimal("36000") and r.data["tope_aplicado"] == "12h"
    assert Decimal(r.data["sin_tope"]) == Decimal("81000") and Decimal(r.data["precio_primera_hora"]) == Decimal("9000")


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
    # ya es playero de un garaje: no se puede volver a agregar
    r = c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": "pepe@test.com"}, format="json")
    assert r.status_code == 400
    # el email de un admin tampoco
    assert c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": admin_garaje.email}, format="json").status_code == 400
    # baja: vuelve a ser conductor y puede seguir usando la app
    assert c.delete(f"/api/garajes/{garaje.id}/playeros/{playero.id}/").status_code == 204
    playero.refresh_from_db()
    assert playero.garaje is None and playero.rol == Rol.CONDUCTOR and playero.is_active


def test_conductor_existente_pasa_a_playero(admin_garaje, garaje, cliente, conductor):
    """Cuenta común creada en la app: el admin la pasa a playero con su email."""
    c = cliente(admin_garaje)
    r = c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": conductor.email}, format="json")
    assert r.status_code == 201
    conductor.refresh_from_db()
    assert conductor.rol == Rol.PLAYERO and conductor.garaje == garaje
    assert cliente(conductor).get("/api/auth/me/").data["rol"] == "PLAYERO"
    # se lo quita y se lo vuelve a agregar, con el email en otro formato
    assert c.delete(f"/api/garajes/{garaje.id}/playeros/{conductor.id}/").status_code == 204
    assert c.post(f"/api/garajes/{garaje.id}/playeros/", {"email": conductor.email.upper()},
                  format="json").status_code == 201


def test_conductor_con_reserva_activa_no_pasa_a_playero(admin_garaje, garaje, cliente, conductor):
    from datetime import timedelta

    from django.utils import timezone
    from django.db.backends.postgresql.psycopg_any import DateTimeTZRange

    from reservas.models import Reserva
    from vehiculos.models import Vehiculo

    ahora = timezone.now()
    vehiculo = Vehiculo.objects.create(conductor=conductor, patente="AB123CD", categoria="AUTO",
                                       categoria_origen="DATACAR", estado_validacion="VALIDADO")
    Reserva.objects.create(conductor=conductor, garaje=garaje, vehiculo=vehiculo, estado="CONFIRMADA", monto=4000,
                           categoria_cobrada="AUTO",
                           periodo=DateTimeTZRange(ahora + timedelta(hours=1), ahora + timedelta(hours=2)))
    r = cliente(admin_garaje).post(f"/api/garajes/{garaje.id}/playeros/", {"email": conductor.email}, format="json")
    assert r.status_code == 400 and "reservas activas" in r.data["email"][0]
    conductor.refresh_from_db()
    assert conductor.rol == Rol.CONDUCTOR


def test_tarifas_del_garaje_se_leen_y_reemplazan(admin_garaje, garaje, cliente):
    c = cliente(admin_garaje)
    url = f"/api/garajes/{garaje.id}/tarifas/"
    hora = {"categoria": "AUTO", "modalidad": "HORA", "precio_fraccion": 320, "fraccion_min": 15,
            "minimo_fracciones": 4, "precio_periodo": None}
    mensual = {"categoria": "AUTO", "modalidad": "MENSUAL", "precio_fraccion": None, "fraccion_min": None,
               "minimo_fracciones": None, "precio_periodo": 150000}
    assert c.put(url, [hora, mensual], format="json").status_code == 200
    assert c.put(url, [hora], format="json").status_code == 200  # lo que no viene deja de ofrecerse
    assert [t["modalidad"] for t in c.get(url).data] == ["HORA"]


def test_tarifas_con_estadia_desde_el_portal(admin_garaje, garaje, cliente):
    """Lo que manda el panel web: primera hora, fracción de 5 min y las dos estadías."""
    c = cliente(admin_garaje)
    url = f"/api/garajes/{garaje.id}/tarifas/"
    hora = {"categoria": "AUTO", "modalidad": "HORA", "precio_primera_hora": 9000, "precio_fraccion": 750,
            "fraccion_min": 5, "minimo_fracciones": 12, "tope_12h": 36000, "tope_24h": 45000, "precio_periodo": None}
    assert c.put(url, [hora], format="json").status_code == 200
    t = c.get(url).data[0]
    assert (Decimal(t["precio_primera_hora"]), Decimal(t["tope_12h"]), Decimal(t["tope_24h"])) == (9000, 36000, 45000)
    r = c.put(url, [{**hora, "tope_24h": 20000}], format="json")
    assert r.status_code == 400 and garaje.tarifas.get().tope_24h == 45000


def test_tarifa_invalida_no_borra_las_existentes(admin_garaje, garaje, cliente):
    c = cliente(admin_garaje)
    url = f"/api/garajes/{garaje.id}/tarifas/"
    Tarifa.objects.create(garaje=garaje, categoria="AUTO", modalidad="HORA", precio_fraccion=320,
                          fraccion_min=15, minimo_fracciones=1)
    malo = {"categoria": "AUTO", "modalidad": "HORA", "precio_fraccion": 0, "fraccion_min": 15, "minimo_fracciones": 1}
    assert c.put(url, [malo], format="json").status_code == 400
    assert garaje.tarifas.count() == 1


def test_tarifas_de_otro_admin_dan_404(otro_admin, garaje, cliente):
    assert cliente(otro_admin).get(f"/api/garajes/{garaje.id}/tarifas/").status_code == 404


def test_foto_del_garaje(garaje, admin_garaje, otro_admin, conductor, cliente, settings, tmp_path):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    salida = BytesIO()
    Image.new("RGB", (2000, 1500), "teal").save(salida, format="JPEG")
    url = f"/api/garajes/{garaje.id}/foto/"
    subir = lambda c: c.put(url, {"foto": SimpleUploadedFile("frente.jpg", salida.getvalue())}, format="multipart")

    assert subir(cliente(otro_admin)).status_code == 404  # sólo el admin del garaje
    r = subir(cliente(admin_garaje))
    assert r.status_code == 200 and r.json()["foto"].startswith("/api/media/garajes/")
    garaje.refresh_from_db()
    with Image.open(garaje.foto.path) as imagen:
        assert imagen.size == (1280, 720)
    primera = garaje.foto.path

    # El conductor la ve en el detalle del garaje
    assert cliente(conductor).get(f"/api/garajes/{garaje.id}/").json()["foto"] == r.json()["foto"]

    # Al reemplazarla o quitarla se borra el archivo anterior
    subir(cliente(admin_garaje))
    garaje.refresh_from_db()
    assert not pathlib.Path(primera).exists()
    assert cliente(admin_garaje).delete(url).json()["foto"] is None
    assert not pathlib.Path(garaje.foto.path).exists()

    malo = cliente(admin_garaje).put(url, {"foto": SimpleUploadedFile("x.jpg", b"no es imagen")}, format="multipart")
    assert malo.status_code == 400
