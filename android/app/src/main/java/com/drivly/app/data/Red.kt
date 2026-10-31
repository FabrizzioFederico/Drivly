package com.drivly.app.data

import com.drivly.app.BuildConfig
import com.drivly.app.data.api.Deuda
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.ErrorApi
import com.drivly.app.data.api.GarajeDisponible
import com.drivly.app.data.api.PedidoRefresh
import com.drivly.app.data.api.Tokens
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit

// encodeDefaults: sin esto kotlinx omite los valores por defecto y {"canal": "app"} viajaría como {}
val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true; encodeDefaults = true }

/** Cliente HTTP: agrega el JWT a cada pedido y, si vence (401), lo renueva una vez con el refresh token. */
fun crearApi(sesion: Sesion, alPerderSesion: () -> Unit): DrivlyApi {
    val cliente = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .addInterceptor { cadena ->
            val pedido = cadena.request().newBuilder()
                .header("Accept", "application/json")
                .header("ngrok-skip-browser-warning", "1") // evita la página de aviso de ngrok en desarrollo
                .apply { sesion.accessBloqueante()?.let { header("Authorization", "Bearer $it") } }
                .build()
            cadena.proceed(pedido)
        }
        .authenticator(RenovadorDeToken(sesion, alPerderSesion))
        .apply {
            if (BuildConfig.DEBUG) addInterceptor(HttpLoggingInterceptor().setLevel(HttpLoggingInterceptor.Level.BASIC))
        }
        .build()

    return Retrofit.Builder()
        .baseUrl(BuildConfig.API_URL)
        .client(cliente)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(DrivlyApi::class.java)
}

private class RenovadorDeToken(private val sesion: Sesion, private val alPerderSesion: () -> Unit) : Authenticator {
    private val sinAuth = OkHttpClient()

    @Synchronized
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.url.encodedPath.contains("/auth/")) return null
        if (response.priorResponse != null) return null // ya se intentó renovar: no insistir
        val usado = response.request.header("Authorization")?.removePrefix("Bearer ")
        val actual = sesion.accessBloqueante()
        // Otro pedido ya lo renovó mientras éste esperaba el lock
        if (actual != null && actual != usado) return response.request.conToken(actual)

        val refresh = sesion.refreshBloqueante() ?: return null.also { alPerderSesion() }
        val cuerpo = json.encodeToString(PedidoRefresh.serializer(), PedidoRefresh(refresh))
            .toRequestBody("application/json".toMediaType())
        val respuesta = try {
            sinAuth.newCall(Request.Builder().url(BuildConfig.API_URL + "auth/refresh/").post(cuerpo).build()).execute()
        } catch (e: IOException) {
            return null
        }
        respuesta.use {
            if (!it.isSuccessful) return null.also { alPerderSesion() }
            val tokens = json.decodeFromString(Tokens.serializer(), it.body!!.string())
            runBlocking { sesion.guardar(tokens.access, tokens.refresh) }
            return response.request.conToken(tokens.access)
        }
    }

    private fun Request.conToken(token: String) = newBuilder().header("Authorization", "Bearer $token").build()
}

/** Error de la API listo para mostrar. `codigo` es el `code` de Drivly (SIN_CUPO, DEUDA_PENDIENTE...). */
class ErrorDrivly(
    mensaje: String,
    val codigo: String? = null,
    val deuda: Deuda? = null,
    val cercanos: List<GarajeDisponible>? = null,
) : Exception(mensaje)

fun Throwable.comoErrorDrivly(): ErrorDrivly = when (this) {
    is ErrorDrivly -> this
    is HttpException -> {
        val cuerpo = response()?.errorBody()?.string().orEmpty()
        val error = runCatching { json.decodeFromString(ErrorApi.serializer(), cuerpo) }.getOrNull()
        when {
            error?.detail != null -> ErrorDrivly(error.detail, error.code, error.deuda, error.cercanos)
            else -> ErrorDrivly(primerErrorDeCampo(cuerpo) ?: "Error del servidor (${code()}). Intentá nuevamente.")
        }
    }
    is IOException -> ErrorDrivly("Sin conexión con Drivly. Revisá tu internet e intentá nuevamente.")
    else -> ErrorDrivly(message ?: "Ocurrió un error inesperado.")
}

/** Errores de validación de DRF: {"patente": ["Esta patente ya está registrada."]} */
private fun primerErrorDeCampo(cuerpo: String): String? = runCatching {
    val objeto = json.parseToJsonElement(cuerpo) as JsonObject
    when (val valor = objeto.values.first()) {
        is JsonArray -> valor.first().jsonPrimitive.content
        is JsonPrimitive -> valor.content
        else -> null
    }
}.getOrNull()
