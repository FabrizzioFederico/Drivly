package com.drivly.app.data.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Endpoints del conductor. Las rutas son relativas a BuildConfig.API_URL (termina en /api/). */
interface DrivlyApi {

    @POST("auth/dev-login/")
    suspend fun devLogin(@Body pedido: PedidoDevLogin = PedidoDevLogin()): RespuestaLogin

    @POST("auth/google/")
    suspend fun googleLogin(@Body pedido: PedidoGoogleLogin): RespuestaLogin

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
    ): List<GarajeDisponible>

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
}
