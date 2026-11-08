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
    # Tipos del registro automotor como los devuelve DataCar
    ("MOTOCICLETA", "MOTO"), ("FURGON", "CAMIONETA"), ("SEDAN 4 PUERTAS", "AUTO"),
    ("RURAL 5 PUERTAS", "AUTO"), ("PICK-UP CABINA DOBLE", "CAMIONETA"), ("TODO TERRENO", "CAMIONETA"),
    ("FURGONETA", "CAMIONETA"), ("CAMION", None), ("", None),
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
    assert r.data["consulta_datacar"] == resultado  # la app arma el mensaje con esto


def test_declarar_y_luego_datacar_prevalece(conductor, cliente, settings, monkeypatch):
    c = cliente(conductor)
    vid = alta(cliente, conductor, "ERR123").data["id"]
    r = c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "CAMIONETA"}, format="json")
    assert r.status_code == 200 and r.data["categoria"] == "CAMIONETA" and r.data["categoria_origen"] == "DECLARADA"

    # DataCar vuelve y dice sedán: reemplaza la declaración y pasa a pagar como auto
    from integraciones import datacar
    monkeypatch.setattr(datacar.SimuladorDataCar, "consultar", lambda self, p: datacar.ResultadoPatente("Sedán"))
    r = c.post(f"/api/vehiculos/{vid}/revalidar/")
    assert r.data["categoria"] == "AUTO" and r.data["categoria_origen"] == "DATACAR"


@pytest.mark.parametrize("patente", ["ERR123", "AB123ZZ", "XX123AB"])
def test_sin_datacar_no_se_puede_declarar_auto(conductor, cliente, patente):
    """Un vivo no puede pagar como auto con una camioneta: "auto" sólo sale de DataCar."""
    vid = alta(cliente, conductor, patente).data["id"]
    r = cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "AUTO"}, format="json")
    assert r.status_code == 400 and "camioneta" in str(r.data["categoria"][0])
    assert Vehiculo.objects.get(id=vid).categoria is None


def test_no_se_puede_declarar_si_datacar_resolvio(conductor, cliente):
    vid = alta(cliente, conductor, "AB123CD").data["id"]
    r = cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "CAMIONETA"}, format="json")
    assert r.status_code == 400


def test_no_se_vuelve_a_declarar(conductor, cliente):
    c = cliente(conductor)
    vid = alta(cliente, conductor, "ERR123").data["id"]
    assert c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "CAMIONETA"}, format="json").status_code == 200
    assert c.post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "CAMIONETA"}, format="json").status_code == 400


def test_no_se_declara_moto(conductor, cliente):
    vid = alta(cliente, conductor, "ERR123").data["id"]
    r = cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "MOTO"}, format="json")
    assert r.status_code == 400


def test_verificacion_del_playero(conductor, cliente):
    """Capa 4: el playero confirma o baja a auto una camioneta declarada."""
    vid = alta(cliente, conductor, "ERR123").data["id"]
    cliente(conductor).post(f"/api/vehiculos/{vid}/declarar/", {"categoria": "CAMIONETA"}, format="json")
    v = Vehiculo.objects.get(id=vid)
    assert verificar_por_playero(v, "CAMIONETA") is False
    assert verificar_por_playero(v, "AUTO") is True
    v.refresh_from_db()
    assert v.categoria == "AUTO" and v.categoria_origen == "VERIFICADA"


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


# --- Integración real con DataCar (sin red: se simula requests.get) ---

class _Respuesta:
    def __init__(self, status, cuerpo, reason="OK"):
        self.status_code, self._cuerpo, self.reason = status, cuerpo, reason
        self.ok = 200 <= status < 300

    def json(self):
        if isinstance(self._cuerpo, Exception):
            raise self._cuerpo
        return self._cuerpo


@pytest.fixture
def datacar_real(settings, monkeypatch):
    """Configura la integración real y devuelve las llamadas hechas a requests.get."""
    from integraciones import datacar

    settings.DATACAR_MOCK = False
    settings.DATACAR_API_URL = ""
    settings.DATACAR_API_KEY = "dca-clave-de-prueba"
    llamadas, respuesta = [], {}

    def falso_get(url, headers, timeout):
        llamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(respuesta["valor"], Exception):
            raise respuesta["valor"]
        return respuesta["valor"]

    monkeypatch.setattr(datacar.requests, "get", falso_get)
    return llamadas, respuesta


def _exito(tipo):
    return _Respuesta(200, {"success": True, "data": {"id": {
        "brand": "RENAULT", "model": "KANGOO II", "year": 2020, "type": tipo, "domestic": True,
    }}, "balance": 99})


def test_datacar_real_arma_la_consulta_y_traduce(datacar_real, conductor, cliente):
    llamadas, respuesta = datacar_real
    respuesta["valor"] = _exito("FURGON")
    r = alta(cliente, conductor, "AB123CD")
    assert r.data["categoria"] == "CAMIONETA" and r.data["categoria_origen"] == "DATACAR"
    assert llamadas == [{
        "url": "https://api.datacar.com.ar/vehicle/ab123cd",
        "headers": {"Authorization": "bearer dca-clave-de-prueba", "Accept": "application/json"},
        "timeout": 3,
    }]
    consulta = Vehiculo.objects.get(id=r.data["id"]).consultas.first()
    assert consulta.resultado == "OK" and consulta.respuesta["data"]["id"]["type"] == "FURGON"
    # el conductor ve qué vehículo encontró DataCar
    assert (r.data["marca"], r.data["modelo"], r.data["anio"], r.data["tipo"]) == ("RENAULT", "KANGOO II", 2020, "FURGON")


def test_datacar_real_tipo_sin_traduccion_igual_muestra_el_vehiculo(datacar_real, conductor, cliente):
    datacar_real[1]["valor"] = _exito("SEMIRREMOLQUE")
    r = alta(cliente, conductor, "AB123CD")
    assert r.data["categoria"] is None and r.data["requiere_declaracion"]
    assert r.data["marca"] == "RENAULT" and r.data["tipo"] == "SEMIRREMOLQUE"


def test_datacar_real_key_sin_prefijo_usa_basic(datacar_real, settings):
    from integraciones.datacar import DataCarGateway

    llamadas, respuesta = datacar_real
    settings.DATACAR_API_KEY = "usuario:clave"
    settings.DATACAR_API_URL = "https://otra.api/v2"
    respuesta["valor"] = _exito("SEDAN 4 PUERTAS")
    assert DataCarGateway().consultar("AB123CD").categoria == "AUTO"
    assert llamadas[0]["url"] == "https://otra.api/v2/vehicle/ab123cd"
    assert llamadas[0]["headers"]["Authorization"] == "basic usuario:clave"


@pytest.mark.parametrize("valor, resultado", [
    (_Respuesta(404, {"error": {"code": 404, "message": "Not found"}}, "Not Found"), "NO_ENCONTRADA"),
    (_Respuesta(200, {"success": False, "data": {}}), "NO_ENCONTRADA"),
    (_Respuesta(401, {"error": {"code": 401, "message": "Invalid token"}}, "Unauthorized"), "ERROR"),
    (_Respuesta(402, {"error": {"code": 402, "message": "Sin saldo"}}, "Payment Required"), "ERROR"),
    (_Respuesta(500, ValueError("no es JSON"), "Server Error"), "ERROR"),
    (__import__("requests").Timeout(), "ERROR"),
    (__import__("requests").ConnectionError(), "ERROR"),
])
def test_datacar_real_fallas_pasan_a_declaracion(datacar_real, conductor, cliente, valor, resultado):
    """CP-16 con la integración real: nada bloquea el alta."""
    datacar_real[1]["valor"] = valor
    r = alta(cliente, conductor, "AB123CD")
    assert r.status_code == 201
    assert r.data["categoria"] is None and r.data["requiere_declaracion"]
    assert Vehiculo.objects.get(id=r.data["id"]).consultas.first().resultado == resultado


def test_datacar_real_sin_key_no_consulta(datacar_real, settings, conductor, cliente):
    llamadas, _ = datacar_real
    settings.DATACAR_API_KEY = ""
    r = alta(cliente, conductor, "AB123CD")
    assert r.data["requiere_declaracion"] and llamadas == []
