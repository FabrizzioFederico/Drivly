import pytest
from django.db import IntegrityError

from vehiculos.models import EstadoValidacion, Vehiculo, normalizar_patente, validar_patente
from django.core.exceptions import ValidationError


@pytest.mark.parametrize("patente", ["ABC123", "ab 123 cd", "AB-123-CD", "123ABC", "a123bcd"])
def test_patentes_validas(patente):
    validar_patente(patente)


@pytest.mark.parametrize("patente", ["AB12", "ABCD123", "A1B2C3", ""])
def test_patentes_invalidas(patente):
    with pytest.raises(ValidationError):
        validar_patente(patente)


def test_normalizar():
    assert normalizar_patente(" ab-123.cd ") == "AB123CD"


def test_alta_valida_y_asigna_categoria(conductor, cliente):
    r = cliente(conductor).post("/api/vehiculos/", {"patente": "ab 123 cd"}, format="json")
    assert r.status_code == 201
    assert r.data["patente"] == "AB123CD"
    assert r.data["estado_validacion"] == "VALIDADO" and r.data["categoria"] in ("AUTO", "CAMIONETA")


def test_moto_por_formato(conductor, cliente):
    r = cliente(conductor).post("/api/vehiculos/", {"patente": "A123BCD"}, format="json")
    assert r.data["categoria"] == "MOTO"


def test_categoria_enviada_por_el_cliente_se_ignora(conductor, cliente):
    """CP-14: el conductor no puede declarar la categoría."""
    r = cliente(conductor).post("/api/vehiculos/", {"patente": "123ABC", "categoria": "AUTO"}, format="json")
    assert r.data["categoria"] == "MOTO"


def test_patente_inexistente_queda_rechazada(conductor, cliente):
    r = cliente(conductor).post("/api/vehiculos/", {"patente": "AB123ZZ"}, format="json")
    assert r.data["estado_validacion"] == "RECHAZADO" and r.data["categoria"] is None


def test_servicio_caido_queda_pendiente_y_se_puede_reintentar(conductor, cliente):
    """CP-16"""
    c = cliente(conductor)
    r = c.post("/api/vehiculos/", {"patente": "ERR123"}, format="json")
    assert r.data["estado_validacion"] == "PENDIENTE"
    v = Vehiculo.objects.get(id=r.data["id"])
    assert v.consultas.first().resultado == "ERROR"
    assert c.post(f"/api/vehiculos/{v.id}/revalidar/").data["estado_validacion"] == "PENDIENTE"


def test_patente_duplicada(conductor, crear_usuario, cliente):
    cliente(conductor).post("/api/vehiculos/", {"patente": "AB123CD"}, format="json")
    otro = crear_usuario("otro@test.com")
    r = cliente(otro).post("/api/vehiculos/", {"patente": "ab123cd"}, format="json")
    assert r.status_code == 400


def test_cada_conductor_ve_solo_los_suyos(conductor, crear_usuario, cliente):
    cliente(conductor).post("/api/vehiculos/", {"patente": "AB123CD"}, format="json")
    otro = crear_usuario("otro@test.com")
    assert cliente(otro).get("/api/vehiculos/").data["count"] == 0


def test_admin_no_accede_a_vehiculos(admin_garaje, cliente):
    assert cliente(admin_garaje).get("/api/vehiculos/").status_code == 403


def test_db_impide_validado_sin_categoria(conductor):
    with pytest.raises(IntegrityError):
        Vehiculo.objects.create(conductor=conductor, patente="AB123CD",
                                estado_validacion=EstadoValidacion.VALIDADO)
