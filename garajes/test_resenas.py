"""Reseñas: sólo califica quien estacionó, una por reserva, y el promedio llega a la búsqueda de la app."""
from datetime import timedelta

import pytest
from freezegun import freeze_time
from django.utils import timezone

from garajes.models import Resena
from operacion.tests import crear_reserva, en, vehiculo  # noqa: F401  (fixture)
from reservas.models import EstadoReserva


def calificar(c, reserva, estrellas, comentario=""):
    return c.put(f"/api/reservas/{reserva.id}/resena/", {"estrellas": estrellas, "comentario": comentario}, format="json")


@pytest.fixture
def terminada(garaje, vehiculo):  # noqa: F811
    return crear_reserva(garaje, vehiculo, en(-180), en(-60), EstadoReserva.FINALIZADA)


def test_califica_una_estadia_terminada_y_la_puede_corregir(cliente, conductor, terminada):
    c = cliente(conductor)
    assert c.get(f"/api/reservas/{terminada.id}/").json()["calificable"] is True
    r = calificar(c, terminada, 4, "  Buena atención  ")
    assert r.status_code == 200 and (r.json()["estrellas"], r.json()["comentario"]) == (4, "Buena atención")

    assert calificar(c, terminada, 5, "Excelente").status_code == 200  # la corrige, no suma otra
    assert Resena.objects.count() == 1 and Resena.objects.get().estrellas == 5
    assert c.get(f"/api/reservas/{terminada.id}/").json()["mis_estrellas"] == 5
    assert c.get(f"/api/reservas/{terminada.id}/resena/").json()["comentario"] == "Excelente"


@pytest.mark.parametrize("estado", [EstadoReserva.CONFIRMADA, EstadoReserva.EN_CURSO, EstadoReserva.CANCELADA])
def test_no_se_califica_sin_haber_estacionado(cliente, conductor, garaje, vehiculo, estado):  # noqa: F811
    reserva = crear_reserva(garaje, vehiculo, en(-180), en(60), estado)
    assert reserva_calificable(cliente(conductor), reserva) is False
    r = calificar(cliente(conductor), reserva, 5)
    assert r.status_code == 409 and r.json()["code"] == "ESTADO_INVALIDO"


def reserva_calificable(c, reserva):
    return c.get(f"/api/reservas/{reserva.id}/").json()["calificable"]


def test_plazo_de_30_dias_y_estrellas_validas(cliente, conductor, terminada):
    c = cliente(conductor)
    assert calificar(c, terminada, 6).status_code == 400
    assert calificar(c, terminada, 0).status_code == 400
    with freeze_time(timezone.now() + timedelta(days=31)):
        assert calificar(c, terminada, 5).status_code == 409


def test_solo_el_conductor_de_la_reserva_califica(cliente, crear_usuario, terminada):
    otro = crear_usuario("otro@test.com")
    assert calificar(cliente(otro), terminada, 1).status_code == 404


def test_listado_con_resumen_y_respuesta_del_admin(cliente, conductor, admin_garaje, otro_admin, garaje, terminada):
    conductor.nombre = "Lucía Fernández"
    conductor.save()
    calificar(cliente(conductor), terminada, 4, "Bien ubicado")
    resena = Resena.objects.get()

    url = f"/api/garajes/{garaje.id}/resenas/{resena.id}/responder/"
    assert cliente(otro_admin).post(url, {"respuesta": "x"}, format="json").status_code == 404
    assert cliente(conductor).post(url, {"respuesta": "x"}, format="json").status_code == 403
    assert cliente(admin_garaje).post(url, {"respuesta": "¡Gracias!"}, format="json").status_code == 200

    datos = cliente(conductor).get(f"/api/garajes/{garaje.id}/resenas/").json()
    assert datos["resumen"] == {"estrellas": 4.0, "cantidad": 1, "por_estrellas": {"5": 0, "4": 1, "3": 0, "2": 0, "1": 0}}
    primera = datos["results"][0]
    assert (primera["autor"], primera["respuesta"]) == ("Lucía F.", "¡Gracias!")
    assert "email" not in str(primera)

    # Si el conductor cambia la reseña, la respuesta era a otro texto: se borra
    calificar(cliente(conductor), terminada, 2, "Me rayaron el auto")
    assert Resena.objects.get().respuesta == ""


def test_promedio_en_el_detalle_y_en_la_busqueda(cliente, conductor, garaje, vehiculo, settings):  # noqa: F811
    settings.DRIVLY_PAGOS_SIMULADOS = True  # sin Mercado Pago conectado igual aparece en la búsqueda
    from garajes.models import Tarifa

    Tarifa.objects.get_or_create(garaje=garaje, categoria="AUTO", modalidad="HORA",
                                 defaults={"precio_fraccion": 1000, "fraccion_min": 15, "minimo_fracciones": 1})
    for estrellas in (5, 4, 4):
        r = crear_reserva(garaje, vehiculo, en(-300), en(-240), EstadoReserva.FINALIZADA)
        calificar(cliente(conductor), r, estrellas)

    detalle = cliente(conductor).get(f"/api/garajes/{garaje.id}/").json()
    assert (detalle["estrellas"], detalle["cantidad_resenas"]) == (4.3, 3)

    inicio = timezone.localtime() + timedelta(days=1)
    busqueda = cliente(conductor).get("/api/garajes/disponibles/", {
        "lat": str(garaje.lat), "lng": str(garaje.lng),
        "inicio": inicio.isoformat(), "fin": (inicio + timedelta(hours=1)).isoformat(),
    }).json()
    assert [(g["estrellas"], g["cantidad_resenas"]) for g in busqueda] == [(4.3, 3)]
