from django.test import TestCase

# Create your tests here.


# ---------- Informe de caja por período (JSON y PDF) ----------

def test_informe_de_caja_y_pdf(cliente, admin_garaje, garaje, crear_usuario):
    from datetime import timedelta as td

    from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
    from django.utils import timezone as tz

    from cuentas.models import Rol
    from operacion.caja import cerrar
    from reservas.models import Reserva

    ahora = tz.now()
    # Dos clientes sin reserva: uno pagó en efectivo y otro sin medio marcado (cuenta como efectivo)
    for patente, medio in (("AB123CD", "EFECTIVO"), ("AC123CD", "")):
        Reserva.objects.create(garaje=garaje, modalidad="PRESENCIAL", estado="FINALIZADA", patente_presencial=patente,
                               salida_estimada=ahora, periodo=DateTimeTZRange(ahora - td(hours=2), ahora - td(minutes=5)),
                               monto=4000, medio_cobro=medio)
    playero = crear_usuario("playero@test.com", rol=Rol.PLAYERO, garaje=garaje)
    cerrar(garaje.id, playero, 7500, "faltan 500")

    url = f"/api/garajes/{garaje.id}/informe/"
    datos = cliente(admin_garaje).get(url).data
    assert datos["total_ingresos"] == "8000.00" and datos["efectivo_cobrado"] == "8000.00"
    assert datos["clientes_sin_reserva"] == 2 and datos["presenciales_sin_medio"] == 1
    assert [c["diferencia"] for c in datos["cierres"]] == ["-500.00"] and datos["diferencia_cierres"] == "-500.00"
    medios = {(f["concepto"], f["medio"]): f["cantidad"] for f in datos["ingresos"]}
    assert medios[("Clientes sin reserva", "Efectivo")] == 1

    pdf = cliente(admin_garaje).get(f"{url}pdf/")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and "attachment" in pdf["Content-Disposition"]

    # Sólo el admin, y con fechas válidas
    assert cliente(playero).get(url).status_code == 403
    assert cliente(admin_garaje).get(url, {"desde": "2026-13-01"}).status_code == 400
    assert cliente(admin_garaje).get(url, {"desde": "2026-11-09", "hasta": "2026-11-01"}).status_code == 400
