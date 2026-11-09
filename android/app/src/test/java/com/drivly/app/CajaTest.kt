package com.drivly.app

import com.drivly.app.data.api.CierreCaja
import com.drivly.app.data.api.ResumenCaja
import com.drivly.app.data.json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CajaTest {
    @Test
    fun `lee el resumen de caja del backend`() {
        val r = json.decodeFromString(ResumenCaja.serializer(), """{
            "desde":"2026-11-09T00:00:00-03:00","hasta":"2026-11-09T21:00:00-03:00","efectivo_esperado":"11000.00",
            "presenciales":{"EFECTIVO":{"cantidad":1,"total":"4000.00"},"MERCADO_PAGO":{"cantidad":1,"total":"4000.00"},
                            "TRANSFERENCIA":{"cantidad":0,"total":"0.00"},"SIN_INDICAR":{"cantidad":1,"total":"4000.00"}},
            "excesos":{"EFECTIVO":{"cantidad":1,"total":"3000.00"}},
            "app":{"cantidad":6,"total":"27800.00"},"ultimo_cierre":null}""")
        assertEquals("11000.00", r.efectivoEsperado)
        assertEquals(1, r.presenciales["SIN_INDICAR"]?.cantidad)
        assertEquals("3000.00", r.excesos["EFECTIVO"]?.total)
        assertNull(r.ultimoCierre)
    }

    @Test
    fun `lee un cierre con faltante`() {
        val c = json.decodeFromString(CierreCaja.serializer(), """{"id":3,"desde":"2026-11-09T00:00:00-03:00",
            "hasta":"2026-11-09T21:00:00-03:00","cerrado_por":"Pepe","efectivo_esperado":"11000.00",
            "efectivo_contado":"10500.00","diferencia":"-500.00","observaciones":"faltó cambio","resumen":{}}""")
        assertEquals("-500.00", c.diferencia)
        assertEquals("Pepe", c.cerradoPor)
    }
}
