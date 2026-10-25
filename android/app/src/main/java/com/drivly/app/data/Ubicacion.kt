package com.drivly.app.data

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.google.android.gms.tasks.Task
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

data class Posicion(val lat: Double, val lng: Double, val esReal: Boolean)

/** Palermo, CABA: el mismo punto que usa la web cuando no hay ubicación. */
val POSICION_DEFECTO = Posicion(-34.5889, -58.4306, esReal = false)

private fun concedido(context: Context, permiso: String) =
    ContextCompat.checkSelfPermission(context, permiso) == PackageManager.PERMISSION_GRANTED

fun tienePermisoDeUbicacion(context: Context) =
    concedido(context, Manifest.permission.ACCESS_COARSE_LOCATION) || concedido(context, Manifest.permission.ACCESS_FINE_LOCATION)

/**
 * Ubicación actual del teléfono, o null si no hay permiso o no se consigue en 10 s.
 * Con permiso preciso se pide al GPS; con aproximado, a la red. Si no responde, la última conocida.
 */
@SuppressLint("MissingPermission") // se verifica con tienePermisoDeUbicacion antes de pedirla
suspend fun ubicacionActual(context: Context): Posicion? {
    if (!tienePermisoDeUbicacion(context)) return null
    val cliente = LocationServices.getFusedLocationProviderClient(context)
    val prioridad = if (concedido(context, Manifest.permission.ACCESS_FINE_LOCATION)) Priority.PRIORITY_HIGH_ACCURACY
    else Priority.PRIORITY_BALANCED_POWER_ACCURACY
    val cancelacion = CancellationTokenSource()
    val actual = withTimeoutOrNull(10_000) { cliente.getCurrentLocation(prioridad, cancelacion.token).esperar() }
    if (actual == null) cancelacion.cancel()
    val ubicacion = actual ?: cliente.lastLocation.esperar()
    return ubicacion?.let { Posicion(it.latitude, it.longitude, esReal = true) }
}

private suspend fun Task<Location?>.esperar(): Location? = suspendCancellableCoroutine { cont ->
    addOnSuccessListener { cont.resume(it) }
    addOnFailureListener { cont.resume(null) }
}
