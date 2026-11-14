package com.drivly.app.data.api

import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.HTTP
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/** Endpoints del conductor y del playero. Las rutas son relativas a BuildConfig.API_URL (termina en /api/). */
interface DrivlyApi {

    @POST("auth/dev-login/")
    suspend fun devLogin(@Body pedido: PedidoDevLogin = PedidoDevLogin()): RespuestaLogin

    @POST("auth/google/")
    suspend fun googleLogin(@Body pedido: PedidoGoogleLogin): RespuestaLogin

    /** Notificaciones push: asocia (o desasocia, al cerrar sesión) este teléfono a la cuenta. */
    @POST("notificaciones/dispositivos/")
    suspend fun registrarDispositivo(@Body pedido: PedidoDispositivo)

    @HTTP(method = "DELETE", path = "notificaciones/dispositivos/", hasBody = true)
    suspend fun borrarDispositivo(@Body pedido: PedidoDispositivo)

    /** Cuenta común: email y contraseña. */
    @POST("auth/login/")
    suspend fun login(@Body pedido: PedidoLogin): RespuestaLogin

    /** Crea la cuenta siempre como conductor, sin activar: llega un email con el link de activación. */
    @POST("auth/registro/")
    suspend fun registro(@Body pedido: PedidoRegistro): RespuestaRegistro

    /** Vuelve a mandar el link de activación (responde igual aunque el email no exista). */
    @POST("auth/activar/reenviar/")
    suspend fun reenviarActivacion(@Body pedido: PedidoEmail): Detalle

    @GET("auth/me/")
    suspend fun yo(): Usuario

    @PATCH("auth/me/")
    suspend fun actualizarPerfil(@Body pedido: PedidoPerfil): Usuario

    /** La foto se guarda recortada en 512x512; devuelve el usuario con la ruta nueva. */
    @Multipart
    @PUT("auth/me/foto/")
    suspend fun subirFoto(@Part foto: MultipartBody.Part): Usuario

    @DELETE("auth/me/foto/")
    suspend fun borrarFoto(): Usuario

    /** Manda un código al email nuevo; el cambio se aplica recién con confirmarEmail. */
    @POST("auth/me/email/")
    suspend fun pedirCambioEmail(@Body pedido: PedidoCambioEmail): Detalle

    @POST("auth/me/email/confirmar/")
    suspend fun confirmarEmail(@Body pedido: PedidoCodigo): Usuario

    /** Mis reservas, la más nueva primero (paginado de a 20). */
    @GET("reservas/")
    suspend fun reservas(@Query("page") pagina: Int = 1): Pagina<Reserva>

    @GET("vehiculos/")
    suspend fun vehiculos(): Pagina<Vehiculo>

    @POST("vehiculos/")
    suspend fun agregarVehiculo(@Body pedido: PedidoVehiculo): Vehiculo

    /** Vuelve a consultar DataCar. */
    @POST("vehiculos/{id}/revalidar/")
    suspend fun revalidarVehiculo(@Path("id") id: String): Vehiculo

    @POST("vehiculos/{id}/declarar/")
    suspend fun declararCategoria(@Path("id") id: String, @Body pedido: PedidoCategoria): Vehiculo

    @GET("garajes/disponibles/")
    suspend fun disponibles(
        @Query("lat") lat: Double,
        @Query("lng") lng: Double,
        @Query("inicio") inicio: String,
        @Query("fin") fin: String,
        @Query("radio") radio: Int = 1000,
        @Query("modalidad") modalidad: String = "HORA",
        /** Con el vehículo, el precio es el de su categoría y no aparecen garajes sin tarifa para él. */
        @Query("vehiculo") vehiculo: String? = null,
    ): List<GarajeDisponible>

    /** Precio estimado sin retener el lugar (se muestra antes del botón "Retener"). */
    @GET("reservas/cotizar/")
    suspend fun cotizar(
        @Query("garaje") garaje: String,
        @Query("vehiculo") vehiculo: String,
        @Query("inicio") inicio: String,
        @Query("fin") fin: String,
        @Query("modalidad") modalidad: String = "HORA",
    ): Cotizacion

    @POST("reservas/hold/")
    suspend fun crearHold(@Body pedido: PedidoHold): Reserva

    @GET("reservas/{id}/")
    suspend fun reserva(@Path("id") id: String): Reserva

    /** Con canal "app" Mercado Pago vuelve por deep link (drivly://pago-resultado). */
    @POST("reservas/{id}/pagar/")
    suspend fun pagar(@Path("id") id: String, @Body pedido: PedidoPago = PedidoPago()): RespuestaPago

    @POST("reservas/{id}/cancelar/")
    suspend fun cancelar(@Path("id") id: String): Reserva

    @GET("reservas/{id}/qr/")
    suspend fun qr(@Path("id") id: String): Qr

    @GET("operacion/mis-deudas/")
    suspend fun misDeudas(): List<Deuda>

    @POST("operacion/mis-deudas/{id}/pagar/")
    suspend fun pagarDeuda(@Path("id") reservaId: String, @Body pedido: PedidoPago = PedidoPago()): RespuestaPago

    // ---------- Playero ----------

    /** Para el playero devuelve sólo su garaje. */
    @GET("garajes/")
    suspend fun misGarajes(): Pagina<GarajeOperado>

    @GET("garajes/{id}/resenas/")
    suspend fun resenas(@Path("id") garajeId: String): PaginaResenas

    /** Crea o corrige la calificación de una estadía terminada. */
    @PUT("reservas/{id}/resena/")
    suspend fun calificar(@Path("id") reservaId: String, @Body pedido: PedidoResena): Resena

    @GET("garajes/{id}/ocupacion/")
    suspend fun ocupacion(@Path("id") garajeId: String): Ocupacion

    /** Garajes con lugar cerca de uno lleno. Sin horario: desde ahora y por 2 horas. */
    @GET("garajes/{id}/cercanos/")
    suspend fun cercanos(
        @Path("id") garajeId: String,
        @Query("inicio") inicio: String? = null,
        @Query("fin") fin: String? = null,
        @Query("modalidad") modalidad: String? = null,
        @Query("vehiculo") vehiculo: String? = null,
    ): List<GarajeDisponible>

    @POST("operacion/ingreso/")
    suspend fun ingreso(@Body pedido: PedidoEscaneo): RespuestaOperacion

    @POST("operacion/egreso/")
    suspend fun egreso(@Body pedido: PedidoEscaneo): RespuestaOperacion

    @POST("operacion/sin-lugar/")
    suspend fun sinLugar(@Body pedido: PedidoEscaneo): RespuestaSinLugar

    @GET("operacion/deudas/{id}/")
    suspend fun estadoDeuda(@Path("id") reservaId: String): EstadoDeuda

    @POST("operacion/deudas/{id}/efectivo/")
    suspend fun cobrarEnEfectivo(@Path("id") reservaId: String): EstadoDeuda

    /** Con qué pagó un cliente sin reserva al salir (efectivo, Mercado Pago o transferencia). */
    @POST("operacion/presencial/{id}/medio/")
    suspend fun marcarMedio(@Path("id") reservaId: String, @Body pedido: PedidoMedio): Reserva

    /** Lo cobrado desde el último cierre de caja del garaje. */
    @GET("operacion/caja/")
    suspend fun caja(@Query("garaje") garajeId: String): ResumenCaja

    @POST("operacion/caja/cerrar/")
    suspend fun cerrarCaja(@Body pedido: PedidoCierre): CierreCaja
}
