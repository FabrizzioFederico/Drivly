package com.drivly.app.ui.reservar

import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.api.Cotizacion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoHold
import com.drivly.app.data.api.PedidoVehiculo
import com.drivly.app.data.api.Reserva
import com.drivly.app.data.api.Vehiculo
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.components.Tarjeta
import com.drivly.app.ui.hora
import com.drivly.app.ui.instante
import com.drivly.app.ui.iso
import com.drivly.app.ui.theme.DrivlyTheme
import com.drivly.app.ui.theme.JetBrainsMono
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

class ReservarViewModel(
    private val api: DrivlyApi,
    private val garajeId: String,
    private val inicio: OffsetDateTime,
    private val fin: OffsetDateTime,
    private val vehiculoInicial: String? = null,
) : ViewModel() {
    var vehiculos by mutableStateOf<List<Vehiculo>>(emptyList())
        private set
    var elegido by mutableStateOf<String?>(null)
        private set
    /** Precio estimado del vehículo elegido, antes de retener (null mientras carga o si falló). */
    var cotizacion by mutableStateOf<Cotizacion?>(null)
        private set
    var reserva by mutableStateOf<Reserva?>(null)
        private set
    var ocupado by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    init {
        cargarVehiculos()
    }

    private fun cargarVehiculos() = tarea {
        vehiculos = api.vehiculos().results
        // El que se usó para buscar (los precios de la lista eran los suyos), o el primero con categoría
        if (elegido == null) {
            (vehiculos.firstOrNull { it.id == vehiculoInicial && it.validado } ?: vehiculos.firstOrNull { it.validado })
                ?.let { elegir(it.id) }
        }
    }

    /** La tarifa depende de la categoría del vehículo: cada cambio vuelve a cotizar. */
    fun elegir(vehiculoId: String) {
        elegido = vehiculoId
        cotizacion = null
        viewModelScope.launch {
            // Si falla no se bloquea nada: el total aparece igual después de retener
            cotizacion = runCatching { api.cotizar(garajeId, vehiculoId, inicio.iso(), fin.iso()) }.getOrNull()
                ?.takeIf { elegido == vehiculoId }
        }
    }

    fun agregarVehiculo(patente: String) = tarea {
        val nuevo = api.agregarVehiculo(PedidoVehiculo(patente))
        vehiculos = vehiculos + nuevo
        if (nuevo.validado) elegir(nuevo.id)
        else error = "No pudimos validar la categoría de ${nuevo.patente}. Declarala desde la web para poder reservar."
    }

    /** CU-04: retiene el lugar 5 minutos mientras el conductor paga. */
    fun retener() = tarea {
        reserva = api.crearHold(PedidoHold(garajeId, elegido!!, inicio.iso(), fin.iso()))
    }

    /** Devuelve el init_point de Mercado Pago (canal "app": vuelve por deep link). */
    fun pagar(abrir: (String) -> Unit) = tarea {
        val respuesta = api.pagar(reserva!!.id)
        respuesta.initPoint?.let(abrir) ?: run { reserva = api.reserva(reserva!!.id) } // pagos simulados: ya confirmada
    }

    fun holdVencido() {
        reserva = null
        error = "Pasaron los 5 minutos y se liberó el lugar. Podés volver a retenerlo."
    }

    private fun tarea(bloque: suspend () -> Unit) {
        ocupado = true
        error = null
        viewModelScope.launch {
            try {
                bloque()
            } catch (e: Exception) {
                error = e.comoErrorDrivly().message
            } finally {
                ocupado = false
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReservarScreen(
    garajeId: String,
    nombre: String,
    direccion: String,
    inicio: OffsetDateTime,
    fin: OffsetDateTime,
    vehiculoId: String?,
    alVolver: () -> Unit,
    alConfirmarSinPago: (String) -> Unit,
) {
    val context = LocalContext.current
    val app = context.applicationContext as DrivlyApplication
    val vm: ReservarViewModel = viewModel { ReservarViewModel(app.api, garajeId, inicio, fin, vehiculoId) }
    val reserva = vm.reserva

    // Con pagos simulados la reserva vuelve confirmada sin pasar por Mercado Pago
    LaunchedEffect(reserva?.estado) { if (reserva?.estado == "CONFIRMADA") alConfirmarSinPago(reserva.id) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(nombre) },
                navigationIcon = {
                    IconButton(onClick = alVolver) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver") }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(direccion, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("De ${hora(inicio.toString())} a ${hora(fin.toString())}", style = MaterialTheme.typography.titleMedium)

            if (reserva == null) {
                SeccionVehiculos(vm)
                vm.cotizacion?.let { PrecioEstimado(it) }
                Button(
                    onClick = vm::retener,
                    enabled = !vm.ocupado && vm.elegido != null,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                ) { Text(if (vm.ocupado) "Reteniendo lugar…" else "Retener lugar por 5 min") }
            } else {
                ResumenHold(reserva, alVencer = vm::holdVencido)
                Button(
                    onClick = {
                        vm.pagar { url -> CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(url)) }
                    },
                    enabled = !vm.ocupado,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = DrivlyTheme.colores.accion,
                        contentColor = MaterialTheme.colorScheme.onSecondary,
                    ),
                ) { Text(if (vm.ocupado) "Abriendo Mercado Pago…" else "Pagar ${ars(reserva.total)} con Mercado Pago") }
            }

            vm.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
        }
    }
}

@Composable
private fun SeccionVehiculos(vm: ReservarViewModel) {
    var patente by remember { mutableStateOf("") }
    Tarjeta {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Vehículo", style = MaterialTheme.typography.titleMedium)
            vm.vehiculos.forEach { v ->
                Row(
                    Modifier.fillMaxWidth()
                        .selectable(selected = vm.elegido == v.id, enabled = v.validado, role = Role.RadioButton,
                            onClick = { vm.elegir(v.id) }),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = vm.elegido == v.id, onClick = null, enabled = v.validado)
                    Spacer(Modifier.padding(4.dp))
                    Text(v.patente, style = MaterialTheme.typography.titleMedium.copy(fontFamily = JetBrainsMono,
                        fontWeight = FontWeight.Bold))
                    Spacer(Modifier.weight(1f))
                    Text(v.categoria ?: "Sin categoría", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            HorizontalDivider()
            OutlinedTextField(
                value = patente,
                onValueChange = { patente = it.uppercase().take(9) },
                label = { Text("Agregar patente") },
                placeholder = { Text("AB123CD") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                textStyle = MaterialTheme.typography.titleMedium.copy(fontFamily = JetBrainsMono),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedButton(
                onClick = { vm.agregarVehiculo(patente.trim()); patente = "" },
                enabled = patente.length >= 6 && !vm.ocupado,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Agregar vehículo") }
            Text("La categoría y la tarifa salen del registro oficial de la patente.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ResumenHold(reserva: Reserva, alVencer: () -> Unit) {
    val vence = remember(reserva.id) { reserva.holdExpiraEn?.let { instante(it).toInstant().toEpochMilli() } ?: 0L }
    var restante by remember(reserva.id) { mutableLongStateOf(vence - System.currentTimeMillis()) }
    LaunchedEffect(reserva.id) {
        while (restante > 0) {
            delay(1000)
            restante = vence - System.currentTimeMillis()
        }
        alVencer()
    }
    // El reloj del teléfono puede diferir unos segundos del servidor: nunca mostrar más de los 5 minutos del hold
    val segundos = (restante / 1000).coerceIn(0, 300)
    Tarjeta {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text(reserva.patente, style = MaterialTheme.typography.titleMedium.copy(fontFamily = JetBrainsMono))
                EstadoChip("HOLD", sufijo = "%02d:%02d".format(segundos / 60, segundos % 60))
            }
            Text("Tu lugar está retenido. Pagá antes de que termine la cuenta regresiva.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Total", style = MaterialTheme.typography.titleMedium)
                Text(ars(reserva.total), style = MaterialTheme.typography.headlineSmall)
            }
        }
    }
}

/** Total estimado antes de retener: el monto definitivo se congela al crear el hold (regla 3). */
@Composable
private fun PrecioEstimado(c: Cotizacion) {
    Tarjeta(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text("Total estimado", style = MaterialTheme.typography.titleMedium)
                Text(ars(c.total), style = MaterialTheme.typography.headlineSmall)
            }
            if (c.fracciones != null && c.precioFraccion != null && c.fraccionMin != null) {
                Text(
                    "${c.fracciones} × ${ars(c.precioFraccion)} (fracciones de ${c.fraccionMin} min)" +
                        if (c.minimoAplicado) " · incluye el mínimo del garaje" else "",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text("Sin cargos extra: la comisión de Drivly la paga el garaje.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
