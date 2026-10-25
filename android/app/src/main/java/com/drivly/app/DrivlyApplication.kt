package com.drivly.app

import android.app.Application
import com.drivly.app.data.Sesion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.crearApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Dependencias compartidas de la app (sin framework de inyección: alcanza para este tamaño). */
class DrivlyApplication : Application() {
    private val alcance = CoroutineScope(SupervisorJob())

    lateinit var sesion: Sesion
        private set
    lateinit var api: DrivlyApi
        private set

    override fun onCreate() {
        super.onCreate()
        sesion = Sesion(this)
        // Si el refresh token venció o fue revocado, se cierra la sesión y la app vuelve al login.
        api = crearApi(sesion) { alcance.launch { sesion.cerrar() } }
    }
}
