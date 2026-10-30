package com.drivly.app.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Formas de la API de Drivly (ver docs/app-android.md). Los montos y coordenadas llegan como texto ("4080.00")
// porque Django los serializa como Decimal: se convierten recién al mostrarlos.

@Serializable
data class Usuario(
    val id: String,
    val email: String,
    val nombre: String = "",
    val rol: String,
    val genero: String = "",
    val telefono: String = "",
    /** Ruta relativa (/api/media/...): se completa con el origen de BuildConfig.API_URL. */
    val foto: String? = null,
)

@Serializable
data class PedidoPerfil(val nombre: String, val genero: String, val telefono: String)

@Serializable
data class PedidoCambioEmail(val email: String)

@Serializable
data class PedidoCodigo(val codigo: String)

@Serializable
data class Detalle(val detail: String = "")

@Serializable
data class RespuestaLogin(val access: String, val refresh: String, val user: Usuario)

@Serializable
data class PedidoDevLogin(val rol: String = "CONDUCTOR")

@Serializable
data class PedidoGoogleLogin(@SerialName("id_token") val idToken: String, val rol: String = "CONDUCTOR")

@Serializable
data class PedidoRefresh(val refresh: String)

@Serializable
data class Tokens(val access: String, val refresh: String? = null)

@Serializable
data class Pagina<T>(val count: Int = 0, val results: List<T> = emptyList())

@Serializable
data class Vehiculo(
    val id: String,
    val patente: String,
    val categoria: String? = null,
    @SerialName("estado_validacion") val estadoValidacion: String,
) {
    val validado get() = estadoValidacion == "VALIDADO"
}

@Serializable
data class PedidoVehiculo(val patente: String)

@Serializable
data class GarajeDisponible(
    val id: String,
    val nombre: String,
    val direccion: String,
    val lat: String,
    val lng: String,
    @SerialName("distancia_m") val distanciaM: Int,
    @SerialName("lugares_libres") val lugaresLibres: Int,
    @SerialName("precio_desde") val precioDesde: String,
    @SerialName("precio_unidad") val precioUnidad: String,
)

@Serializable
data class GarajeResumen(val id: String, val nombre: String, val direccion: String, val lat: String, val lng: String)

@Serializable
data class PedidoHold(
    val garaje: String,
    val vehiculo: String,
    val inicio: String,
    val fin: String,
    val modalidad: String = "HORA",
)

@Serializable
data class Reserva(
    val id: String,
    @SerialName("garaje_detalle") val garaje: GarajeResumen? = null,
    val patente: String = "",
    val categoria: String? = null,
    val modalidad: String = "HORA",
    val inicio: String,
    val fin: String,
    val estado: String,
    @SerialName("hold_expira_en") val holdExpiraEn: String? = null,
    val total: String,
    @SerialName("cancelable_hasta") val cancelableHasta: String? = null,
    /** Sólo en la respuesta de cancelar: REEMBOLSADO, REEMBOLSO_FALLIDO o null. */
    val reembolso: String? = null,
)

@Serializable
data class Cotizacion(
    val total: String,
    val fracciones: Int? = null,
    @SerialName("fraccion_min") val fraccionMin: Int? = null,
    @SerialName("precio_fraccion") val precioFraccion: String? = null,
    @SerialName("minimo_aplicado") val minimoAplicado: Boolean = false,
)

@Serializable
data class Deuda(
    @SerialName("reserva_id") val reservaId: String,
    @SerialName("garaje_nombre") val garajeNombre: String,
    val patente: String,
    @SerialName("minutos_excedidos") val minutosExcedidos: Int,
    @SerialName("egreso_real") val egresoReal: String,
    val total: String,
)

@Serializable
data class PedidoPago(val canal: String = "app")

@Serializable
data class RespuestaPago(@SerialName("init_point") val initPoint: String? = null, val estado: String? = null)

@Serializable
data class Qr(
    @SerialName("qr_token") val qrToken: String,
    @SerialName("valido_desde") val validoDesde: String,
    @SerialName("valido_hasta") val validoHasta: String,
    val reutilizable: Boolean = false,
)

@Serializable
data class ErrorApi(val detail: String? = null, val code: String? = null)
