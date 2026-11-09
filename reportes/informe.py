"""
Informe de caja de un garaje para un período (CU-10): ingresos por medio, excesos, reembolsos, comisión de Drivly
y los cierres de caja del playero. Usa el mismo cálculo que el cierre (operacion.caja), así los números coinciden.
"""
import io
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from operacion.caja import SIN_INDICAR, resumen
from operacion.models import Deuda, EstadoDeuda, MedioCobro
from pagos.models import Pago, ResultadoPago
from reservas.models import EstadoReserva, Modalidad, Reserva

CERO = Decimal("0.00")
NOMBRE_MEDIO = {**{m.value: m.label for m in MedioCobro}, SIN_INDICAR: "Sin indicar (se cuenta como efectivo)"}


def _dec(valor):
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _limites(desde, hasta):
    ini = timezone.make_aware(datetime.combine(desde, time.min))
    return ini, timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))


def informe(garaje, desde, hasta):
    """`desde` y `hasta` son fechas locales, las dos incluidas."""
    ini, fin = _limites(desde, hasta)
    caja = resumen(garaje, ini, fin)

    filas = [{"concepto": "Reservas y abonos por la app", "medio": "Mercado Pago",
              "cantidad": caja["app"]["cantidad"], "total": caja["app"]["total"]}]
    for concepto, clave in (("Clientes sin reserva", "presenciales"), ("Excesos de permanencia", "excesos")):
        for medio, datos in caja[clave].items():
            if datos["cantidad"]:
                filas.append({"concepto": concepto, "medio": NOMBRE_MEDIO[medio], **datos})
    total = sum((_dec(f["total"]) for f in filas), CERO)

    pagos = Pago.objects.filter(reserva__garaje=garaje, creado_en__gte=ini, creado_en__lt=fin)
    comision = _dec(pagos.filter(resultado__in=(ResultadoPago.CONFIRMO_RESERVA, ResultadoPago.SALDO_DEUDA))
                    .aggregate(t=Sum("comision"))["t"])
    reembolsos = Pago.objects.filter(reserva__garaje=garaje, resultado=ResultadoPago.REEMBOLSADO,
                                     actualizado_en__gte=ini, actualizado_en__lt=fin)
    deudas = Deuda.objects.filter(reserva__garaje=garaje)
    condonado = _dec(deudas.filter(egreso_real__gte=ini, egreso_real__lt=fin).aggregate(t=Sum("monto_condonado"))["t"])
    cierres = garaje.cierres.select_related("cerrado_por").filter(hasta__gte=ini, hasta__lt=fin).order_by("hasta")

    return {
        "garaje": garaje.nombre, "cuit": garaje.cuit, "desde": desde, "hasta": hasta,
        "ingresos": filas,
        "total_ingresos": str(total),
        "comision_drivly": str(comision),
        "neto_garaje": str(total - comision),  # antes de la tarifa de Mercado Pago, que depende de cada cuenta
        "efectivo_cobrado": caja["efectivo_esperado"],
        "reembolsos": {"cantidad": reembolsos.count(), "total": str(_dec(reembolsos.aggregate(t=Sum("monto"))["t"]))},
        "condonado": str(condonado),
        "cancelaciones": Reserva.objects.filter(garaje=garaje, estado=EstadoReserva.CANCELADA,
                                                creada_en__gte=ini, creada_en__lt=fin).count(),
        "excesos_generados": deudas.filter(egreso_real__gte=ini, egreso_real__lt=fin).count(),
        "deuda_pendiente": str(_dec(deudas.filter(estado__in=(EstadoDeuda.PENDIENTE, EstadoDeuda.INCOBRABLE))
                                    .aggregate(t=Sum("monto"))["t"])),
        "presenciales_sin_medio": caja["presenciales"][SIN_INDICAR]["cantidad"],
        "cierres": [{
            "fecha": c.hasta, "cerrado_por": c.cerrado_por.nombre or c.cerrado_por.email,
            "efectivo_esperado": str(c.efectivo_esperado), "efectivo_contado": str(c.efectivo_contado),
            "diferencia": str(c.diferencia), "observaciones": c.observaciones,
        } for c in cierres],
        "diferencia_cierres": str(sum((c.diferencia for c in cierres), CERO)),
        "reservas_por_app": caja["app"]["cantidad"],
        "clientes_sin_reserva": Reserva.objects.filter(
            garaje=garaje, modalidad=Modalidad.PRESENCIAL, estado=EstadoReserva.FINALIZADA,
            periodo__endswith__gte=ini, periodo__endswith__lt=fin).count(),
    }


# ---------- PDF ----------

def pesos(valor) -> str:
    entero, centavos = f"{_dec(valor):,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"${entero}" if centavos == "00" else f"${entero},{centavos}"


TEAL = colors.HexColor("#00796B")
GRIS = colors.HexColor("#5b6670")
LINEA = colors.HexColor("#d9dee2")


def _tabla(filas, anchos, alinear_derecha=(), negrita_ultima=False):
    t = Table(filas, colWidths=anchos, repeatRows=1)
    estilo = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, GRIS),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for col in alinear_derecha:
        estilo.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    if negrita_ultima:
        estilo += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.8, GRIS)]
    t.setStyle(TableStyle(estilo))
    return t


def pdf(datos) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Informe de caja · {datos['garaje']}", author="Drivly")
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=base["Title"], alignment=0, fontSize=18, spaceAfter=2)
    sub = ParagraphStyle("s", parent=base["Normal"], textColor=GRIS, fontSize=9.5)
    seccion = ParagraphStyle("h", parent=base["Heading2"], fontSize=12, textColor=TEAL, spaceBefore=12, spaceAfter=6)
    nota = ParagraphStyle("n", parent=base["Normal"], textColor=GRIS, fontSize=8, leading=10)
    ancho = A4[0] - 36 * mm

    periodo = f"{datos['desde']:%d/%m/%Y}" + ("" if datos["desde"] == datos["hasta"] else f" al {datos['hasta']:%d/%m/%Y}")
    hoy = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    hist = [
        Paragraph(f"Informe de caja · {datos['garaje']}", titulo),
        Paragraph(f"CUIT {datos['cuit']} · Período {periodo} · Generado el {hoy} con Drivly", sub),
        Spacer(1, 8),
    ]

    resumen_filas = [
        ["Total cobrado", pesos(datos["total_ingresos"])],
        ["Comisión de Drivly (retenida por Mercado Pago)", f"- {pesos(datos['comision_drivly'])}"],
        ["Neto para el garaje", pesos(datos["neto_garaje"])],
        ["Efectivo cobrado (debería estar en la caja)", pesos(datos["efectivo_cobrado"])],
        ["Diferencia de los cierres de caja", pesos(datos["diferencia_cierres"])],
    ]
    t = Table(resumen_filas, colWidths=[ancho * 0.7, ancho * 0.3])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    hist += [Paragraph("Resumen", seccion), t]

    ingresos = [["Concepto", "Medio", "Cant.", "Total"]] + [
        [f["concepto"], f["medio"], str(f["cantidad"]), pesos(f["total"])] for f in datos["ingresos"]
    ] + [["Total", "", "", pesos(datos["total_ingresos"])]]
    hist += [Paragraph("Ingresos por medio", seccion),
             _tabla(ingresos, [ancho * 0.38, ancho * 0.34, ancho * 0.1, ancho * 0.18], (2, 3), negrita_ultima=True)]

    otros = [
        ["Concepto", "Valor"],
        ["Reservas por la app", str(datos["reservas_por_app"])],
        ["Clientes sin reserva", str(datos["clientes_sin_reserva"])],
        ["Excesos de permanencia generados", str(datos["excesos_generados"])],
        ["Excesos condonados", pesos(datos["condonado"])],
        ["Reservas canceladas", str(datos["cancelaciones"])],
        [f"Reembolsos ({datos['reembolsos']['cantidad']})", pesos(datos["reembolsos"]["total"])],
        ["Deuda pendiente al día de hoy", pesos(datos["deuda_pendiente"])],
    ]
    hist += [Paragraph("Actividad", seccion), _tabla(otros, [ancho * 0.7, ancho * 0.3], (1,))]

    hist.append(Paragraph("Cierres de caja", seccion))
    if datos["cierres"]:
        cierres = [["Fecha", "Cerró", "Esperado", "Contado", "Diferencia"]] + [[
            timezone.localtime(c["fecha"]).strftime("%d/%m %H:%M"), c["cerrado_por"], pesos(c["efectivo_esperado"]),
            pesos(c["efectivo_contado"]), pesos(c["diferencia"]),
        ] for c in datos["cierres"]] + [["Total", "", "", "", pesos(datos["diferencia_cierres"])]]
        hist.append(_tabla(cierres, [ancho * 0.16, ancho * 0.3, ancho * 0.18, ancho * 0.18, ancho * 0.18], (2, 3, 4),
                           negrita_ultima=True))
        con_nota = [c for c in datos["cierres"] if c["observaciones"]]
        for c in con_nota:
            hist.append(Paragraph(f"{timezone.localtime(c['fecha']):%d/%m %H:%M} · {c['observaciones']}", nota))
    else:
        hist.append(Paragraph("No hubo cierres de caja en el período.", sub))

    avisos = ["La diferencia de un cierre es lo contado menos lo esperado: negativa es faltante.",
              "El neto no descuenta la tarifa de Mercado Pago, que depende de los plazos de cada cuenta."]
    if datos["presenciales_sin_medio"]:
        avisos.insert(0, f"{datos['presenciales_sin_medio']} cobro(s) a clientes sin reserva no tienen medio marcado: "
                         "se cuentan como efectivo.")
    hist += [Spacer(1, 14)] + [Paragraph(a, nota) for a in avisos]
    doc.build(hist)
    return buffer.getvalue()
