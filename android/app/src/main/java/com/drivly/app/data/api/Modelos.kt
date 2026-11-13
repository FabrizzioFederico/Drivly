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

/** Sin dato de DataCar el conductor sólo puede declarar camioneta (la tarifa más cara). */
private const val SIN_DATO_CAMIONETA = "Sin ese dato sólo podés reservar con la tarifa de camioneta."

@Serializable
data class Vehiculo(
    val id: String,
    val patente: String,
    val categoria: String? = null,
    @SerialName("estado_validacion") val estadoValidacion: String,
    /** Si DataCar no la resolvió, el conductor declara auto o camioneta (regla 3). */
    @SerialName("puede_declarar") val puedeDeclarar: Boolean = false,
    /** Lo que encontró DataCar para esa patente; vacío si no respondió. */
    val marca: String = "",
    val modelo: String = "",
    val anio: Int? = null,
    val tipo: String = "",
    /** Foto ilustrativa del modelo (Wikimedia Commons) y su crédito, que la licencia CC BY-SA obliga a mostrar. */
    @SerialName("imagen_url") val imagenUrl: String = "",
    @SerialName("imagen_credito") val imagenCredito: String = "",
    /** Última consulta a DataCar: OK, NO_ENCONTRADA o ERROR (null si no se consultó, como en las motos). */
    @SerialName("consulta_datacar") val consultaDatacar: String? = null,
) {
    val validado get() = estadoValidacion == "VALIDADO"
    val rechazado get() = estadoValidacion == "RECHAZADO"

    /**
     * "Peugeot 504 — © Joost J. Bakker (CC BY 2.0), via Wikimedia Commons" -> "© Joost J. Bakker · CC BY 2.0 ·
     * Wikimedia Commons": sin el modelo (ya está arriba) y corto para una línea. Si cambia el formato, va tal cual.
     */
    val creditoFoto: String?
        get() {
            val sinModelo = imagenCredito.substringAfter(" — ", imagenCredito).trim()
            val partes = Regex("""^(©\s*.+?)\s*\((CC[^)]*)\),?\s*(?:via\s+)?(.*)$""").find(sinModelo)?.groupValues
            return (partes?.drop(1)?.filter { it.isNotBlank() }?.joinToString(" · ") ?: sinModelo).ifBlank { null }
        }

    /** Por qué todavía no tiene categoría, para mostrarle al conductor. */
    val motivoSinCategoria: String
        get() = when (consultaDatacar) {
            "NO_ENCONTRADA" ->
                "La patente $patente no figura en el registro automotor. Revisá que esté bien escrita. " +
                    SIN_DATO_CAMIONETA
            "ERROR" ->
                "No pudimos consultar el registro automotor en este momento. Reintentá en unos minutos. " +
                    SIN_DATO_CAMIONETA
            "OK" -> "La patente $patente figura como ${tipo.lowercase().ifBlank { "otro tipo de vehículo" }}" +
                (descripcion?.let { " ($it)" } ?: "") + ": no es auto, camioneta ni moto. " + SIN_DATO_CAMIONETA
            else -> "Todavía no pudimos validar la patente $patente con el registro automotor. " + SIN_DATO_CAMIONETA
        }

    /** "RENAULT KANGOO II · 2020", o null si DataCar no devolvió datos. */
    val descripcion: String?
        get() = listOf(marca, modelo).filter { it.isNotBlank() }.joinToString(" ").ifBlank { null }
            ?.let { nombre -> anio?.let { "$nombre · $it" } ?: nombre }
}

/** Token de Firebase Cloud Messaging del teléfono. */
@Serializable
data class PedidoDispositivo(val token: String, val plataforma: String = "android")

@Serializable
data class PedidoLogin(val email: String, val password: String)

@Serializable
data class PedidoRegistro(val nombre: String, val email: String, val password: String)

/** La cuenta nueva queda sin activar: no trae sesión, sólo el aviso del email con el link. */
@Serializable
data class RespuestaRegistro(
    val detail: String,
    val email: String,
    @SerialName("email_enviado") val emailEnviado: Boolean = true,
)

@Serializable
data class PedidoEmail(val email: String)

@Serializable
data class PedidoCategoria(val categoria: String)

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
    val foto: String? = null, // ruta relativa (/api/media/...) que carga el admin desde la web
)

@Serializable
data class GarajeResumen(
    val id: String, val nombre: String, val direccion: String, val lat: String, val lng: String, val foto: String? = null,
)

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
    /** Clientes sin reserva: con qué pagó al salir (EFECTIVO, MERCADO_PAGO, TRANSFERENCIA o vacío). */
    @SerialName("medio_cobro") val medioCobro: String = "",
)

// ---------- Caja del playero ----------

@Serializable
data class PedidoMedio(val garaje: String, val medio: String)

@Serializable
data class TotalMedio(val cantidad: Int = 0, val total: String = "0.00")

/** Lo cobrado desde el último cierre. Las claves de los mapas: EFECTIVO, MERCADO_PAGO, TRANSFERENCIA, SIN_INDICAR. */
@Serializable
data class ResumenCaja(
    val desde: String,
    val hasta: String,
    @SerialName("efectivo_esperado") val efectivoEsperado: String,
    val presenciales: Map<String, TotalMedio> = emptyMap(),
    val excesos: Map<String, TotalMedio> = emptyMap(),
    val app: TotalMedio = TotalMedio(),
    @SerialName("ultimo_cierre") val ultimoCierre: CierreCaja? = null,
)

@Serializable
data class CierreCaja(
    val id: Int,
    val desde: String,
    val hasta: String,
    @SerialName("cerrado_por") val cerradoPor: String = "",
    @SerialName("efectivo_esperado") val efectivoEsperado: String,
    @SerialName("efectivo_contado") val efectivoContado: String,
    val diferencia: String,
    val observaciones: String = "",
)

@Serializable
data class PedidoCierre(
    val garaje: String,
    @SerialName("efectivo_contado") val efectivoContado: String,
    val observaciones: String = "",
)

@Serializable
data class Cotizacion(
    val total: String,
    val fracciones: Int? = null,
    @SerialName("fraccion_min") val fraccionMin: Int? = null,
    @SerialName("precio_fraccion") val precioFraccion: String? = null,
    @SerialName("minimo_aplicado") val minimoAplicado: Boolean = false,
    /** Precio de la primera hora completa, si el garaje la cobra aparte de las fracciones. */
    @SerialName("precio_primera_hora") val precioPrimeraHora: String? = null,
    /** "12h" o "24h" si se cobró la estadía (más barata que las fracciones); `sinTope` es lo que habría salido. */
    @SerialName("tope_aplicado") val topeAplicado: String? = null,
    @SerialName("sin_tope") val sinTope: String? = null,
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
