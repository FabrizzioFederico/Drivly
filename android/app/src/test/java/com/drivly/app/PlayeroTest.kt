package com.drivly.app

import com.drivly.app.data.api.ErrorApi
import com.drivly.app.data.api.Ocupacion
import com.drivly.app.data.api.PedidoEscaneo
import com.drivly.app.data.api.RespuestaOperacion
import com.drivly.app.data.json
import com.drivly.app.ui.playero.Nivel
import com.drivly.app.ui.playero.esPatente
import com.drivly.app.ui.playero.horasLabel
import com.drivly.app.ui.playero.limpiarPatente
import com.drivly.app.ui.playero.nivelPresencial
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlayeroTest {
    @Test
    fun reconocePatentesComoLaWeb() {
        assertTrue(esPatente("ab 123 cd"))
        assertTrue(esPatente("A123BCD"))
        assertTrue(esPatente("abc-123"))
        assertFalse(esPatente("eyJhbGciOi"))
        assertEquals("AB123CD", limpiarPatente(" ab-123 cd "))
    }

    @Test
    fun semaforoSegunLugaresParaClientesSinReserva() {
        assertEquals(Nivel.ROJO, nivelPresencial(0, 20))
        assertEquals(Nivel.AMBAR, nivelPresencial(2, 20))
        assertEquals(Nivel.VERDE, nivelPresencial(3, 20))
    }

    @Test
    fun etiquetaDeSalida() {
        assertEquals("2 h", horasLabel(120))
        assertEquals("90 min", horasLabel(90))
    }

    @Test
    fun escaneoMandaSoloLoQueCorresponde() {
        assertEquals("""{"garaje":"g","qr_token":"t"}""",
            json.encodeToString(PedidoEscaneo.serializer(), PedidoEscaneo("g", qrToken = "t")))
    }

    @Test
    fun ocupacionConAlertas() {
        val o = json.decodeFromString(Ocupacion.serializer(),
            """{"capacidad":20,"ocupados_app":3,"ocupados_abonos":1,"ocupados_presencial":2,"proximas_app":1,
               "ventana_min":120,"libres":14,"libres_presencial":13,"umbral_alerta":0.9,"franjas":[],
               "alertas_overstay":[{"reserva_id":"r","patente":"AB123CD","inicio":"2026-10-30T18:00:00Z"}]}""")
        assertEquals("AB123CD", o.alertasOverstay.single().patente)
    }

    @Test
    fun egresoConDeuda() {
        val r = json.decodeFromString(RespuestaOperacion.serializer(),
            """{"reserva":{"id":"r","origen":"APP","inicio":"2026-10-30T18:00:00Z","fin":"2026-10-30T19:00:00Z",
                 "estado":"CON_DEUDA","total":"4080.00"},
               "deuda":$DEUDA,"ocupacion":null}""")
        assertEquals("0.50", r.deuda?.recargo)
        assertEquals("https://mp/qr", r.deuda?.mpQrData)
    }

    @Test
    fun deudaDeOtroGarajeSoloPorQr() {
        val e = json.decodeFromString(ErrorApi.serializer(),
            """{"detail":"Deuda","code":"DEUDA_PATENTE","deuda":${DEUDA.dropLast(1)},"efectivo":false}}""")
        assertEquals("DEUDA_PATENTE", e.code)
        assertFalse(e.deuda!!.efectivo)
    }

    private companion object {
        const val DEUDA = """{"reserva_id":"r","patente":"AB123CD","minutos_excedidos":20,"tolerancia_min":10,
            "fraccion_min":15,"fracciones":2,"precio_fraccion":"500.00","recargo":"0.50","total":"1500.00",
            "mp_qr_data":"https://mp/qr","fin_reservado":"2026-10-30T19:00:00Z","egreso_real":"2026-10-30T19:30:00Z",
            "garaje_nombre":"Centro","estado":"PENDIENTE","monto_condonado":"0.00","motivo_condonacion":""}"""
    }
}
