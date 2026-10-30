package com.drivly.app.data.api

import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/** Endpoints del conductor. Las rutas son relativas a BuildConfig.API_URL (termina en /api/). */
interface DrivlyApi {

    @POST("auth/dev-login/")
    suspend fun devLogin(@Body pedido: PedidoDevLogin = PedidoDevLogin()): RespuestaLogin

    @POST("auth/google/")
    suspend fun googleLogin(@Body pedido: PedidoGoogleLogin): RespuestaLogin

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
}
