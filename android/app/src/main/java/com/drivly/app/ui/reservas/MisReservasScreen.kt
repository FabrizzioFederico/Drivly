package com.drivly.app.ui.reservas

import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.api.Deuda
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.Reserva
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.components.LocalEspacioBarra
import com.drivly.app.ui.components.Tarjeta
import com.drivly.app.ui.fechaHora
import com.drivly.app.ui.hora
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

/** Estados con ticket (QR) para mostrar. */
private val CON_TICKET = setOf("CONFIRMADA", "EN_CURSO")

class MisReservasViewModel(private val api: DrivlyApi) : ViewModel() {
    var reservas by mutableStateOf<List<Reserva>?>(null)
        private set
    var deudas by mutableStateOf<List<Deuda>>(emptyList())
        private set
    var actualizando by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var pagando by mutableStateOf(false)
        private set
    var errorPago by mutableStateOf<String?>(null)
        private set

    fun cargar() {
        actualizando = true
        error = null
        viewModelScope.launch {
            try {
                deudas = api.misDeudas()
                reservas = api.reservas().results
            } catch (e: Exception) {
                error = e.comoErrorDrivly().message
            } finally {
                actualizando = false
            }
        }
    }

    /** Devuelve el init_point de Mercado Pago (canal "app": vuelve por deep link). */
    fun pagarDeuda(deuda: Deuda, abrir: (String) -> Unit) {
        pagando = true
        errorPago = null
        viewModelScope.launch {
            try {
                api.pagarDeuda(deuda.reservaId).initPoint?.let(abrir) ?: cargar() // pagos simulados: ya saldada
            } catch (e: Exception) {
                errorPago = e.comoErrorDrivly().message
            } finally {
                pagando = false
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MisReservasScreen(alAbrirTicket: (String) -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val context = LocalContext.current
    val vm: MisReservasViewModel = viewModel { MisReservasViewModel(app.api) }
    LaunchedEffect(Unit) { vm.cargar() } // al volver a la pestaña se refresca (puede haber cambiado un estado)

    Scaffold(topBar = { TopAppBar(title = { Text("Mis reservas") }) }) { padding ->
        PullToRefreshBox(
            isRefreshing = vm.actualizando && vm.reservas != null,
            onRefresh = vm::cargar,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            val reservas = vm.reservas
            when {
                reservas == null && vm.error == null -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
                reservas == null -> Column(Modifier.fillMaxSize(), Arrangement.Center, Alignment.CenterHorizontally) {
                    Text(vm.error!!, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(24.dp))
                    TextButton(onClick = vm::cargar) { Text("Reintentar") }
                }
                reservas.isEmpty() -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Text("Todavía no hiciste reservas.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                else -> LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + LocalEspacioBarra.current),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(vm.deudas, key = { "deuda-${it.reservaId}" }) { d ->
                        TarjetaDeuda(d, vm.errorPago, vm.pagando) {
                            vm.pagarDeuda(d) { url -> CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(url)) }
                        }
                    }
                    items(reservas, key = { it.id }) { r -> FilaReserva(r, alAbrirTicket) }
                }
            }
        }
    }
}

/**
 * Un hold vencido ya no ocupa lugar, pero figura HOLD hasta que la tarea de Celery lo pasa a EXPIRADA
 * (corre cada minuto en producción): se muestra como expirado para no confundir al conductor.
 */
private fun estadoVisible(r: Reserva): String {
    val vencido = r.holdExpiraEn?.let { OffsetDateTime.parse(it).isBefore(OffsetDateTime.now()) } == true
    return if (r.estado == "HOLD" && vencido) "EXPIRADA" else r.estado
}

/** CU-09: mientras exista, la cuenta no puede reservar, así que va arriba de todo y con el botón de pago. */
@Composable
private fun TarjetaDeuda(d: Deuda, error: String?, pagando: Boolean, alPagar: () -> Unit) {
    Tarjeta(Modifier.fillMaxWidth(), borde = BorderStroke(1.dp, MaterialTheme.colorScheme.error)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Deuda pendiente · ${ars(d.total)}", style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.error)
            Text("${d.garajeNombre} · ${d.patente}. Saliste ${d.minutosExcedidos} min después del horario " +
                "reservado (${fechaHora(d.egresoReal)}). Saldala para volver a reservar.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = alPagar, enabled = !pagando, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Text("Pagar ${ars(d.total)}")
            }
        }
    }
}

@Composable
private fun FilaReserva(r: Reserva, alAbrirTicket: (String) -> Unit) {
    val conTicket = r.estado in CON_TICKET
    Tarjeta(Modifier.fillMaxWidth(), onClick = if (conTicket) ({ alAbrirTicket(r.id) }) else null) {
        ListItem(
            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
            overlineContent = { EstadoChip(estadoVisible(r)) },
            headlineContent = { Text(r.garaje?.nombre ?: "Reserva", style = MaterialTheme.typography.titleMedium) },
            supportingContent = {
                Text("${fechaHora(r.inicio)} a ${hora(r.fin)} · ${r.patente} · ${ars(r.total)}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            },
            trailingContent = if (conTicket) ({ Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Ver ticket") }) else null,
        )
    }
}
