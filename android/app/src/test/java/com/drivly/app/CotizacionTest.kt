package com.drivly.app

import com.drivly.app.data.api.Cotizacion
import com.drivly.app.data.json
import com.drivly.app.ui.reservar.detallePrecio
import org.junit.Assert.assertTrue
import org.junit.Test

class CotizacionTest {
    private fun cotizacion(cuerpo: String) = json.decodeFromString(Cotizacion.serializer(), cuerpo)

    @Test
    fun `9 horas con estadia explica el tope`() {
        val c = cotizacion("""{"total":"36000.00","fracciones":108,"fraccion_min":5,"precio_fraccion":"750.00",
            "precio_primera_hora":"9000.00","tope_aplicado":"12h","sin_tope":"81000.00"}""")
        val texto = detallePrecio(c)!!
        assertTrue(texto, texto.startsWith("Estadía de hasta 12 h") && texto.contains("81.000"))
    }

    @Test
    fun `hora y media es primera hora mas fracciones`() {
        val c = cotizacion("""{"total":"13500.00","fracciones":18,"fraccion_min":5,"precio_fraccion":"750.00",
            "precio_primera_hora":"9000.00"}""")
        val texto = detallePrecio(c)!!
        assertTrue(texto, texto.startsWith("Primera hora") && texto.contains("+ 6 ×") && texto.contains("cada 5 min"))
    }

    @Test
    fun `tarifa vieja sigue mostrando fracciones`() {
        val c = cotizacion("""{"total":"4000.00","fracciones":4,"fraccion_min":15,"precio_fraccion":"1000.00"}""")
        assertTrue(detallePrecio(c)!!.startsWith("4 ×"))
    }
}
