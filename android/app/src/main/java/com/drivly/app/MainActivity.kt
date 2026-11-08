package com.drivly.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.drivly.app.ui.DrivlyApp
import com.drivly.app.ui.theme.DrivlyTheme
import kotlinx.coroutines.flow.MutableStateFlow

class MainActivity : ComponentActivity() {
    /** Último deep link de Mercado Pago sin procesar (drivly://pago-resultado?...). */
    private val deepLinks = MutableStateFlow<Uri?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen() // antes de super.onCreate: muestra la "P" de Drivly mientras arranca la app
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) recibir(intent)
        setContent {
            DrivlyTheme {
                DrivlyApp(deepLinks, alConsumirDeepLink = { deepLinks.value = null })
            }
        }
    }

    // launchMode="singleTop": al volver de la Custom Tab llega acá en lugar de abrir otra instancia
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        recibir(intent)
    }

    private fun recibir(intent: Intent?) {
        // Al tocar una notificación push llegan sus datos como extras: se pasan a drivly://aviso?tipo=...&reserva_id=...
        val tipo = intent?.getStringExtra("tipo")
        val reservaId = intent?.getStringExtra("reserva_id")
        if (tipo != null && reservaId != null) {
            deepLinks.value = Uri.parse("drivly://aviso?tipo=${Uri.encode(tipo)}&reserva_id=${Uri.encode(reservaId)}")
            return
        }
        val uri = intent?.data ?: return
        if (uri.scheme == "drivly" && uri.host == "pago-resultado") deepLinks.value = uri
    }
}
