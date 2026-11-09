package com.drivly.app

import com.drivly.app.data.api.Vehiculo
import com.drivly.app.data.json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VehiculoTest {
    private fun vehiculo(cuerpo: String) = json.decodeFromString(Vehiculo.serializer(), cuerpo)

    @Test
    fun `muestra marca, modelo y año de DataCar`() {
        val v = vehiculo("""{"id":"1","patente":"AB123CD","categoria":"CAMIONETA","estado_validacion":"VALIDADO",
            "marca":"RENAULT","modelo":"KANGOO II","anio":2020,"tipo":"FURGON","consulta_datacar":"OK"}""")
        assertEquals("RENAULT KANGOO II · 2020", v.descripcion)
    }

    @Test
    fun `credito de la foto corto y sin el modelo`() {
        val v = vehiculo("""{"id":"1","patente":"ABC123","estado_validacion":"VALIDADO",
            "imagen_url":"https://cdn.trustcar.info/x.jpg",
            "imagen_credito":"Peugeot 504 — © Joost J. Bakker (CC BY 2.0), via Wikimedia Commons"}""")
        assertEquals("© Joost J. Bakker · CC BY 2.0 · Wikimedia Commons", v.creditoFoto)
    }

    @Test
    fun `credito con otro formato se muestra tal cual y sin foto no hay credito`() {
        val v = vehiculo("""{"id":"1","patente":"ABC123","estado_validacion":"VALIDADO","imagen_credito":"Foto de Juan"}""")
        assertEquals("Foto de Juan", v.creditoFoto)
        assertNull(vehiculo("""{"id":"1","patente":"ABC123","estado_validacion":"VALIDADO"}""").creditoFoto)
    }

    @Test
    fun `sin datos de DataCar no hay descripcion`() {
        assertNull(vehiculo("""{"id":"1","patente":"A123BCD","estado_validacion":"VALIDADO"}""").descripcion)
    }

    @Test
    fun `patente inexistente pide revisarla`() {
        val v = vehiculo("""{"id":"1","patente":"AB123ZZ","estado_validacion":"PENDIENTE","consulta_datacar":"NO_ENCONTRADA"}""")
        assertTrue(v.motivoSinCategoria.startsWith("La patente AB123ZZ no figura en el registro automotor"))
    }

    @Test
    fun `falla de DataCar pide reintentar`() {
        val v = vehiculo("""{"id":"1","patente":"ERR123","estado_validacion":"PENDIENTE","consulta_datacar":"ERROR"}""")
        assertTrue(v.motivoSinCategoria.startsWith("No pudimos consultar el registro automotor"))
    }

    @Test
    fun `tipo sin categoria explica que vehiculo encontro`() {
        val v = vehiculo("""{"id":"1","patente":"AB123CD","estado_validacion":"PENDIENTE","consulta_datacar":"OK",
            "marca":"CORMETAL","modelo":"S-2","anio":2017,"tipo":"SEMIRREMOLQUE"}""")
        assertEquals("La patente AB123CD figura como semirremolque (CORMETAL S-2 · 2017): no es auto, camioneta ni moto. " +
            "Sin ese dato sólo podés reservar con la tarifa de camioneta.", v.motivoSinCategoria)
    }
}
