package com.drivly.app.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.util.Log
import com.drivly.app.BuildConfig
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoDispositivo
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * Notificaciones push con Firebase Cloud Messaging. Firebase se inicializa con los datos de local.properties
 * (sin google-services.json): si faltan, la app funciona igual y sólo no recibe push.
 */
object Push {
    const val CANAL_RESERVAS = "reservas"
    const val CANAL_DEUDAS = "deudas"
    private const val TAG = "DrivlyPush"

    val configurado: Boolean
        get() = BuildConfig.FIREBASE_APP_ID.isNotBlank() && BuildConfig.FIREBASE_PROJECT_ID.isNotBlank()

    fun iniciar(context: Context) {
        crearCanales(context)
        if (!configurado || FirebaseApp.getApps(context).isNotEmpty()) return
        val opciones = FirebaseOptions.Builder()
            .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
            .setApplicationId(BuildConfig.FIREBASE_APP_ID)
            .setApiKey(BuildConfig.FIREBASE_API_KEY)
            .setGcmSenderId(BuildConfig.FIREBASE_SENDER_ID)
            .build()
        FirebaseApp.initializeApp(context, opciones)
    }

    /** Canales de Android 8+: el usuario puede silenciar los recordatorios de reservas sin perder los de deudas. */
    private fun crearCanales(context: Context) {
        val gestor = context.getSystemService(NotificationManager::class.java) ?: return
        gestor.createNotificationChannels(listOf(
            NotificationChannel(CANAL_RESERVAS, "Reservas y pagos", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Confirmaciones, recordatorios de inicio y fin, y reembolsos"
            },
            NotificationChannel(CANAL_DEUDAS, "Deudas", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Excesos de permanencia pendientes de pago"
            },
        ))
    }

    private suspend fun token(): String? {
        if (!configurado) return null
        return suspendCancellableCoroutine { cont ->
            FirebaseMessaging.getInstance().token.addOnCompleteListener { tarea ->
                cont.resume(if (tarea.isSuccessful) tarea.result else null)
            }
        }
    }

    /** Al ingresar (y cada vez que abre la app): el backend asocia este teléfono a la cuenta. */
    suspend fun registrar(api: DrivlyApi, token: String? = null) {
        val actual = token ?: token() ?: return
        runCatching { api.registrarDispositivo(PedidoDispositivo(actual)) }
            .onFailure { Log.w(TAG, "No se pudo registrar el teléfono para push", it) }
    }

    /** Al cerrar sesión: que el teléfono deje de recibir los avisos de esa cuenta. */
    suspend fun olvidar(api: DrivlyApi) {
        val actual = token() ?: return
        runCatching { api.borrarDispositivo(PedidoDispositivo(actual)) }
    }
}
