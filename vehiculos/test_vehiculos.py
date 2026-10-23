import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from integraciones.datacar import categoria_desde_clasificacion
from vehiculos.models import Vehiculo, normalizar_patente, validar_patente
from vehiculos.services import verificar_por_playero


@pytest.mark.parametrize("patente", ["ABC123", "ab 123 cd", "AB-123-CD", "123ABC", "a123bcd"])
def test_patentes_validas(patente):
    validar_patente(patente)


@pytest.mark.parametrize("patente", ["AB12", "ABCD123", "A1B2C3", ""])
def test_patentes_invalidas(patente):
    with pytest.raises(ValidationError):
        validar_patente(patente)


def test_normalizar():
    assert normalizar_patente(" ab-123.cd ") == "AB123CD"


@pytest.mark.parametrize("clasificacion, categoria", [
    ("Sedán", "AUTO"), ("SUV", "CAMIONETA"), ("Pick-up", "CAMIONETA"), ("pick up", "CAMIONETA"),
    ("Furgón", "CAMIONETA"), ("Motocicleta", "MOTO"), ("Casa rodante", None),
])
def test_traduccion_de_clasificacion_datacar(clasificacion, categoria):
    assert categoria_desde_clasificacion(clasificacion) == categoria


def alta(cliente, conductor, patente, **extra):
    return cliente(conductor).post("/api/vehiculos/", {"patente": patente, **extra}, format="json")


def test_auto_resuelto_por_datacar(conductor, cliente):
    r = alta(cliente, conductor, "ab 123 cd")
    assert r.status_code == 201 and r.data["patente"] == "AB123CD"
    assert r.data["categoria"] == "AUTO" and r.data["categoria_origen"] == "DATACAR"
    assert r.data["requiere_declaracion"] is False and r.data["puede_declarar"] is False


def test_suv_es_camioneta(conductor, cliente):
    assert alta(cliente, conductor, "AE123BC").data["categoria"] == "CAMIONETA"


def test_moto_por_formato_sin_consultar(conductor, cliente):
    """CP-28: la moto se resuelve aunque DataCar esté caído."""
    r = alta(cliente, conductor, "A123BCD")
    assert r.data["categoria"] == "MOTO" and r.data["categoria_origen"] == "FORMATO"
    assert not Vehiculo.objects.get(id=r.data["id"]).consultas.exists()


def test_categoria_enviada_en_el_alta_se_ignora(conductor, cliente):
    """CP-14"""
    assert alta(cliente, conductor, "AE111AA", categoria="AUTO").data["categoria"] == "CAMIONETA"


@pytest.mark.parametrize("patente, resultado", [("ERR123", "ERROR"), ("AB123ZZ", "NO_ENCONTRADA"), ("XX123AB", "OK")])
def test_sin_dato_de_datacar_queda_para_declarar(conductor, cliente, patente, resultado):
    """CP-16: caída, dominio inexistente o clasificación sin traducción -> respaldo por declaración."""
    r = alta(cliente, conductor, patente)
    assert r.data["categoria"] is None and r.data["requiere_declaracion"] and r.data["puede_declarar"]
    assert Vehiculo.objects.get(id=r.data["id"]).consultas.first().resultado == resultado


def test_declarar_y_luego_datacar_prevalece(conductor, cliente, settings, monkeypatch):
    c = cliente(conductor)
    vid = alta(cliente, conductor, "ERR123").data["id"]
    r = c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json")
    assert r.status_code == 200 and r.data["categoria_origen"] == "DECLARADA"

    # DataCar vuelve y dice SUV: reemplaza la declaración
    from integraciones import datacar
    monkeypatch.setattr(datacar.SimuladorDataCar, "consultar", lambda self, p: datacar.ResultadoPatente("SUV"))
    r = c.post(f"/api/vehiculos/{vid}/revalidar/")
    assert r.data["categoria"] == "CAMIONETA" and r.data["categoria_origen"] == "DATACAR"


def test_no_se_puede_declarar_si_datacar_resolvio(conductor, cliente):
    vid = alta(cliente, conductor, "AB123CD").data["id"]
    r = cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json")
    assert r.status_code == 400


def test_no_se_declara_moto(conductor, cliente):
    vid = alta(cliente, conductor, "ERR123").data["id"]
    r = cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "MOTO"}, format="json")
    assert r.status_code == 400


def test_dos_correcciones_bloquean_la_declaracion(conductor, cliente):
    """CP-29 y regla 3: con dos correcciones del playero la cuenta ya no declara."""
    c = cliente(conductor)
    for patente in ("ERR111", "ERR222"):
        vid = alta(cliente, conductor, patente).data["id"]
        c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json")
        assert verificar_por_playero(Vehiculo.objects.get(id=vid), "CAMIONETA") is True
    conductor.refresh_from_db()
    assert conductor.correcciones_categoria == 2
    vid = alta(cliente, conductor, "ERR333").data["id"]
    assert c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json").status_code == 403


def test_verificacion_confirma_sin_contar_correccion(conductor, cliente):
    vid = alta(cliente, conductor, "ERR123").data["id"]
    cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json")
    assert verificar_por_playero(Vehiculo.objects.get(id=vid), "AUTO") is False
    conductor.refresh_from_db()
    assert conductor.correcciones_categoria == 0


def test_patente_duplicada(conductor, crear_usuario, cliente):
    alta(cliente, conductor, "AB123CD")
    assert alta(cliente, crear_usuario("otro@test.com"), "ab123cd").status_code == 400


def test_cada_conductor_ve_solo_los_suyos(conductor, crear_usuario, cliente):
    alta(cliente, conductor, "AB123CD")
    assert cliente(crear_usuario("otro@test.com")).get("/api/vehiculos/").data["count"] == 0


def test_admin_no_accede_a_vehiculos(admin_garaje, cliente):
    assert cliente(admin_garaje).get("/api/vehiculos/").status_code == 403


def test_db_impide_categoria_sin_origen(conductor):
    with pytest.raises(IntegrityError):
        Vehiculo.objects.create(conductor=conductor, patente="AB123CD", categoria="AUTO", estado_validacion="VALIDADO")
