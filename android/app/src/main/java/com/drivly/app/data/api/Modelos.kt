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
    /** APP o PRESENCIAL (cliente sin reserva, sólo lo ve el playero). */
    val origen: String = "APP",
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
    // Lo que usa el playero para cobrarla
    @SerialName("tolerancia_min") val toleranciaMin: Int = 0,
    @SerialName("fraccion_min") val fraccionMin: Int = 15,
    val fracciones: Int = 0,
    @SerialName("precio_fraccion") val precioFraccion: String = "0",
    /** Porcentaje: "0.50" = +50 %. */
    val recargo: String = "0",
    @SerialName("monto_condonado") val montoCondonado: String = "0",
    @SerialName("fin_reservado") val finReservado: String? = null,
    /** init_point para mostrar como QR; vacío si Mercado Pago no está disponible. */
    @SerialName("mp_qr_data") val mpQrData: String = "",
    /** false en otro garaje (CP-30): la deuda es del que la generó y sólo se cobra por QR. */
    val efectivo: Boolean = true,
)

@Serializable
data class GarajeOperado(val id: String, val nombre: String)

@Serializable
data class AlertaOverstay(
    @SerialName("reserva_id") val reservaId: String,
    val patente: String,
    val inicio: String,
)

/** Semáforo del playero (regla 6): `libresPresencial` es cuántos clientes sin reserva pueden entrar ahora. */
@Serializable
data class Ocupacion(
    val capacidad: Int,
    val libres: Int,
    @SerialName("libres_presencial") val libresPresencial: Int,
    @SerialName("ocupados_app") val ocupadosApp: Int,
    @SerialName("ocupados_abonos") val ocupadosAbonos: Int = 0,
    @SerialName("ocupados_presencial") val ocupadosPresencial: Int,
    @SerialName("proximas_app") val proximasApp: Int,
    @SerialName("ventana_min") val ventanaMin: Int,
    @SerialName("alertas_overstay") val alertasOverstay: List<AlertaOverstay> = emptyList(),
)

/** Ingreso, egreso o sin lugar: va el QR o la patente; la salida estimada sólo en clientes sin reserva. */
@Serializable
data class PedidoEscaneo(
    val garaje: String,
    @SerialName("qr_token") val qrToken: String? = null,
    val patente: String? = null,
    @SerialName("salida_estimada") val salidaEstimada: String? = null,
)

@Serializable
data class RespuestaOperacion(val reserva: Reserva, val deuda: Deuda? = null, val ocupacion: Ocupacion? = null)

@Serializable
data class Reembolso(val monto: String, val estado: String)

@Serializable
data class RespuestaSinLugar(
    val reserva: Reserva,
    val reembolso: Reembolso,
    val cercanos: List<GarajeDisponible> = emptyList(),
)

@Serializable
data class EstadoDeuda(val pagado: Boolean, @SerialName("transaccion_id") val transaccionId: String? = null)

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
data class ErrorApi(
    val detail: String? = null,
    val code: String? = null,
    /** En DEUDA_PATENTE: la deuda a cobrar antes del ingreso. */
    val deuda: Deuda? = null,
    /** En SIN_LUGAR_PRESENCIAL: garajes a los que derivar al cliente. */
    val cercanos: List<GarajeDisponible>? = null,
)
