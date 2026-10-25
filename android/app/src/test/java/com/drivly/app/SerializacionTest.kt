package com.drivly.app

import com.drivly.app.data.api.PedidoHold
import com.drivly.app.data.api.PedidoPago
import com.drivly.app.data.api.Reserva
import com.drivly.app.data.json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Los pedidos tienen que viajar con sus valores por defecto: el backend decide el retorno de MP según `canal`. */
class SerializacionTest {
    @Test
    fun pagoDesdeLaAppMandaElCanal() {
        assertEquals("""{"canal":"app"}""", json.encodeToString(PedidoPago.serializer(), PedidoPago()))
    }

    @Test
    fun holdMandaLaModalidad() {
        val cuerpo = json.encodeToString(PedidoHold.serializer(), PedidoHold("g", "v", "2026-10-25T00:00Z", "2026-10-25T03:00Z"))
        assertEquals(true, cuerpo.contains(""""modalidad":"HORA""""))
    }

    @Test
    fun reservaIgnoraCamposQueNoUsamos() {
        val r = json.decodeFromString(Reserva.serializer(),
            """{"id":"r1","inicio":"2026-10-25T00:00:00Z","fin":"2026-10-25T03:00:00Z","estado":"HOLD","total":"4080.00",
               "desglose":{"fracciones":12},"cancelable_hasta":null}""")
        assertEquals("4080.00", r.total)
        assertNull(r.cancelableHasta)
    }
}
