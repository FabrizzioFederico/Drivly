package com.drivly.app.ui.buscar

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.DrivlyApplication
import com.drivly.app.ui.components.Tarjeta
import com.drivly.app.data.Sesion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.GarajeDisponible
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.hora
import com.drivly.app.ui.iso
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit

/** Mientras no pidamos permiso de ubicación se busca alrededor del mismo punto que usa la web (Palermo). */
private const val LAT_DEFECTO = -34.5889
private const val LNG_DEFECTO = -58.4306

/** Horario elegido; viaja a la pantalla de reserva. */
data class Horario(val inicio: OffsetDateTime, val horas: Int) {
    val fin: OffsetDateTime get() = inicio.plusHours(horas.toLong())

    companion object {
        /** Ahora redondeado al próximo cuarto de hora, como defaultHorario() de la web. */
        fun desdeAhora(horas: Int = 3): Horario {
            val ahora = OffsetDateTime.now().truncatedTo(ChronoUnit.MINUTES)
            val resto = ahora.minute % 15
            return Horario(if (resto == 0) ahora else ahora.plusMinutes((15 - resto).toLong()), horas)
        }
    }
}

class BuscarViewModel(private val api: DrivlyApi, private val sesion: Sesion) : ViewModel() {
    var horario by mutableStateOf(Horario.desdeAhora())
        private set
    var garajes by mutableStateOf<List<GarajeDisponible>>(emptyList())
        private set
    var cargando by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    fun elegirHoras(horas: Int) {
        horario = Horario.desdeAhora(horas)
        buscar()
    }

    fun buscar() {
        cargando = true
        error = null
        viewModelScope.launch {
            try {
                garajes = api.disponibles(LAT_DEFECTO, LNG_DEFECTO, horario.inicio.iso(), horario.fin.iso())
            } catch (e: Exception) {
                error = e.comoErrorDrivly().message
            } finally {
                cargando = false
            }
        }
    }

    fun cerrarSesion() = viewModelScope.launch { sesion.cerrar() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BuscarScreen(alElegir: (GarajeDisponible, Horario) -> Unit, mensaje: String?, alMostrarMensaje: () -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val vm: BuscarViewModel = viewModel { BuscarViewModel(app.api, app.sesion) }
    LaunchedEffect(Unit) { if (vm.garajes.isEmpty()) vm.buscar() }
    val avisos = remember { SnackbarHostState() }
    LaunchedEffect(mensaje) {
        if (mensaje != null) {
            alMostrarMensaje()
            avisos.showSnackbar(mensaje)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(avisos) },
        topBar = {
            TopAppBar(
                title = { Text("Estacionar cerca") },
                actions = {
                    IconButton(onClick = { vm.cerrarSesion() }) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Cerrar sesión")
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Desde las ${hora(vm.horario.inicio.toString())} hasta las ${hora(vm.horario.fin.toString())}",
                    style = MaterialTheme.typography.titleMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(1, 2, 3, 6).forEach { h ->
                        FilterChip(selected = vm.horario.horas == h, onClick = { vm.elegirHoras(h) },
                            label = { Text("$h h") })
                    }
                }
            }

            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                when {
                    vm.cargando -> CircularProgressIndicator()
                    vm.error != null -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(vm.error!!, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center,
                            modifier = Modifier.padding(24.dp))
                        TextButton(onClick = vm::buscar) { Text("Reintentar") }
                    }
                    vm.garajes.isEmpty() -> Text("No hay garajes con Drivly en esta zona para ese horario.",
                        textAlign = TextAlign.Center, modifier = Modifier.padding(24.dp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    else -> LazyColumn(
                        Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        items(vm.garajes, key = { it.id }) { g ->
                            TarjetaGaraje(g, onClick = { alElegir(g, vm.horario) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TarjetaGaraje(g: GarajeDisponible, onClick: () -> Unit) {
    val lleno = g.lugaresLibres <= 0
    Tarjeta(Modifier.fillMaxWidth(), onClick = onClick, enabled = !lleno) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(g.nombre, style = MaterialTheme.typography.titleMedium)
                Text("${g.distanciaM} m", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(g.direccion, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Desde ${ars(g.precioDesde)} ${g.precioUnidad}", style = MaterialTheme.typography.titleSmall)
                Text(
                    if (lleno) "Sin lugar" else "${g.lugaresLibres} libres",
                    style = MaterialTheme.typography.labelLarge,
                    color = if (lleno) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}
