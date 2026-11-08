package com.drivly.app

import android.Manifest
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.drivly.app.data.Push
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Recibe los push de Drivly. Con la app cerrada o en segundo plano Android muestra la notificación solo
 * y al tocarla abre MainActivity con los datos como extras; con la app abierta la mostramos acá.
 */
class PushService : FirebaseMessagingService() {
    private val alcance = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        val app = applicationContext as DrivlyApplication
        alcance.launch {
            if (app.sesion.logueado.first()) Push.registrar(app.api, token)
        }
    }

    override fun onMessageReceived(mensaje: RemoteMessage) {
        val aviso = mensaje.notification ?: return
        val permitido = android.os.Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        if (!permitido) return

        val abrir = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            mensaje.data.forEach { (clave, valor) -> putExtra(clave, valor) }
        }
        val alTocar = PendingIntent.getActivity(
            this, mensaje.messageId.hashCode(), abrir, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notificacion = NotificationCompat.Builder(this, aviso.channelId ?: Push.CANAL_RESERVAS)
            .setSmallIcon(R.drawable.ic_notificacion)
            .setContentTitle(aviso.title)
            .setContentText(aviso.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(aviso.body))
            .setContentIntent(alTocar)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(this).notify(mensaje.messageId.hashCode(), notificacion)
    }
}
