package com.drivly.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

private val Context.almacen by preferencesDataStore(name = "drivly")

/**
 * Tokens JWT y QR guardados en el teléfono (DataStore). El QR queda guardado para mostrarlo sin señal.
 * El access se mantiene en memoria para no leer disco en cada pedido.
 */
class Sesion(private val context: Context) {
    private val claveAccess = stringPreferencesKey("access")
    private val claveRefresh = stringPreferencesKey("refresh")
    private val claveNombre = stringPreferencesKey("nombre")

    @Volatile private var accessEnMemoria: String? = null

    val logueado: Flow<Boolean> = context.almacen.data.map { it[claveRefresh] != null }
    val nombre: Flow<String> = context.almacen.data.map { it[claveNombre].orEmpty() }

    suspend fun guardar(access: String, refresh: String?, nombre: String? = null) {
        accessEnMemoria = access
        context.almacen.edit { p ->
            p[claveAccess] = access
            if (refresh != null) p[claveRefresh] = refresh // el refresh rota: siempre guardar el último
            if (nombre != null) p[claveNombre] = nombre
        }
    }

    suspend fun cerrar() {
        accessEnMemoria = null
        context.almacen.edit { it.clear() }
    }

    /** Lo usan los interceptores de OkHttp, que corren en hilos de red (bloquear ahí es aceptable). */
    fun accessBloqueante(): String? = accessEnMemoria ?: runBlocking { context.almacen.data.first()[claveAccess] }
        .also { accessEnMemoria = it }

    fun refreshBloqueante(): String? = runBlocking { context.almacen.data.first()[claveRefresh] }

    suspend fun guardarQr(reservaId: String, json: String) {
        context.almacen.edit { it[stringPreferencesKey("qr.$reservaId")] = json }
    }

    suspend fun qrGuardado(reservaId: String): String? = context.almacen.data.first()[stringPreferencesKey("qr.$reservaId")]

    suspend fun borrarQr(reservaId: String) {
        context.almacen.edit { it.remove(stringPreferencesKey("qr.$reservaId")) }
    }
}
