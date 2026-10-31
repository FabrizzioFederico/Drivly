package com.drivly.app.ui.buscar

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.BottomSheetScaffold
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberBottomSheetScaffoldState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.POSICION_DEFECTO
import com.drivly.app.data.Posicion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.GarajeDisponible
import com.drivly.app.data.api.Vehiculo
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.data.tienePermisoDeUbicacion
import com.drivly.app.data.ubicacionActual
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.ListaCercanos
import com.drivly.app.ui.components.LocalEspacioBarra
import com.drivly.app.ui.components.Tarjeta
import com.drivly.app.ui.components.bordeOscuro
import com.drivly.app.ui.iso
import com.drivly.app.ui.theme.DrivlyTheme
import com.drivly.app.ui.theme.JetBrainsMono
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit

/** Horario elegido; viaja a la pantalla de reserva. En un abono el fin sale de la modalidad, como en el backend. */
data class Horario(val inicio: OffsetDateTime, val horas: Int, val modalidad: String = "HORA") {
    val fin: OffsetDateTime
        get() = when (modalidad) {
            "SEMANAL" -> inicio.plusWeeks(1)
            "MENSUAL" -> inicio.plusMonths(1)
            "ANUAL" -> inicio.plusYears(1)
            else -> inicio.plusHours(horas.toLong())
        }

    companion object {
        /** Ahora redondeado al próximo cuarto de hora, como defaultHorario() de la web. */
        fun desdeAhora(horas: Int = 3): Horario {
            val ahora = OffsetDateTime.now().truncatedTo(ChronoUnit.MINUTES)
            val resto = ahora.minute % 15
            return Horario(if (resto == 0) ahora else ahora.plusMinutes((15 - resto).toLong()), horas)
        }
    }
}

class BuscarViewModel(private val api: DrivlyApi) : ViewModel() {
    var posicion by mutableStateOf(POSICION_DEFECTO)
        private set
    var horario by mutableStateOf(Horario.desdeAhora())
        private set
    var garajes by mutableStateOf<List<GarajeDisponible>>(emptyList())
        private set
    var elegido by mutableStateOf<String?>(null)
    /** Vehículos con categoría: sólo con ellos se puede reservar. */
    var vehiculos by mutableStateOf<List<Vehiculo>>(emptyList())
        private set
    var vehiculo by mutableStateOf<Vehiculo?>(null)
        private set
    private var vehiculosCargados = false
    var cargando by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    /** Garaje lleno que tocó el conductor: en vez de bloquearlo se le ofrecen los cercanos (regla 6). */
    var lleno by mutableStateOf<GarajeDisponible?>(null)
        private set
    /** null mientras se buscan. */
    var cercanos by mutableStateOf<List<GarajeDisponible>?>(null)
        private set

    fun verCercanos(g: GarajeDisponible) {
        lleno = g
        cercanos = null
        viewModelScope.launch {
            cercanos = runCatching {
                api.cercanos(g.id, horario.inicio.iso(), horario.fin.iso(), horario.modalidad, vehiculo?.id)
            }.getOrDefault(emptyList())
        }
    }

    fun volverALaLista() {
        lleno = null
    }

    fun cambiarHorario(nuevo: Horario) {
        horario = nuevo
        buscar()
    }

    fun ubicar(nueva: Posicion) {
        posicion = nueva
        buscar()
    }

    fun elegirVehiculo(v: Vehiculo) {
        vehiculo = v
        buscar()
    }

    fun buscar() {
        cargando = true
        error = null
        lleno = null
        viewModelScope.launch {
            try {
                if (!vehiculosCargados) {
                    // Si falla, se busca igual sin vehículo (precios "desde")
                    vehiculos = runCatching { api.vehiculos().results.filter { it.validado } }.getOrDefault(emptyList())
                    vehiculo = vehiculos.firstOrNull()
                    vehiculosCargados = true
                }
                garajes = api.disponibles(posicion.lat, posicion.lng, horario.inicio.iso(), horario.fin.iso(),
                    modalidad = horario.modalidad, vehiculo = vehiculo?.id)
                if (garajes.none { it.id == elegido }) elegido = null
            } catch (e: Exception) {
                error = e.comoErrorDrivly().message
            } finally {
                cargando = false
            }
        }
    }
}

private val PERMISOS_UBICACION = arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION)

/** Alto de la hoja plegada: el encabezado y la primera tarjeta, sin tapar demasiado el mapa. */
private val ALTO_HOJA = 220.dp
/** Lo que ocupa la tarjeta del horario sobre el mapa (para que el encuadre no deje garajes debajo). */
private val ALTO_HORARIO = 210.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BuscarScreen(alElegir: (GarajeDisponible, Horario, Vehiculo?) -> Unit, mensaje: String?, alMostrarMensaje: () -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as DrivlyApplication
    val vm: BuscarViewModel = viewModel { BuscarViewModel(app.api) }
    val alcance = rememberCoroutineScope()
    val avisos = remember { SnackbarHostState() }
    val lista = rememberLazyListState()
    val hoja = rememberBottomSheetScaffoldState(snackbarHostState = avisos)
    // BottomSheetScaffold no deja lugar para la barra de gestos ni para la barra flotante: se suma a mano
    val debajo = LocalEspacioBarra.current + WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val asomaHoja = ALTO_HOJA + debajo

    fun ubicarConGps() = alcance.launch {
        val real = ubicacionActual(context)
        if (real != null) vm.ubicar(real)
        else avisos.showSnackbar("No pudimos obtener tu ubicación. Te mostramos garajes en Palermo.")
    }

    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        if (r.values.any { it }) ubicarConGps()
        else alcance.launch { avisos.showSnackbar("Sin permiso de ubicación te mostramos garajes en Palermo.") }
    }

    LaunchedEffect(Unit) {
        if (vm.garajes.isNotEmpty()) return@LaunchedEffect
        vm.buscar() // mientras tanto, alrededor de Palermo
        if (tienePermisoDeUbicacion(context)) ubicarConGps() else pedirPermiso.launch(PERMISOS_UBICACION)
    }
    LaunchedEffect(mensaje) {
        if (mensaje != null) {
            alMostrarMensaje()
            avisos.showSnackbar(mensaje)
        }
    }
    // Tocar un punto del mapa lleva la lista hasta su tarjeta
    LaunchedEffect(vm.elegido) {
        val i = vm.garajes.indexOfFirst { it.id == vm.elegido }
        if (i >= 0) lista.animateScrollToItem(i)
    }

    BottomSheetScaffold(
        scaffoldState = hoja,
        sheetPeekHeight = asomaHoja,
        topBar = {
            TopAppBar(
                title = { Text("Estacionar cerca") },
                actions = { SelectorVehiculo(vm.vehiculos, vm.vehiculo, vm::elegirVehiculo) },
            )
        },
        snackbarHost = { SnackbarHost(avisos) },
        sheetContent = { HojaGarajes(vm, lista, debajo, alElegir) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(top = padding.calculateTopPadding())) {
            MapaGarajes(
                posicion = vm.posicion,
                garajes = vm.garajes,
                elegido = vm.elegido,
                alElegir = { vm.elegido = it },
                margenSuperior = ALTO_HORARIO,
                margenInferior = asomaHoja,
                margenDerecho = 56.dp, // botón de ubicación
                modifier = Modifier.fillMaxSize(),
            )
            Surface(
                modifier = Modifier.fillMaxWidth().padding(12.dp),
                shape = MaterialTheme.shapes.large,
                color = if (DrivlyTheme.colores.oscuro) MaterialTheme.colorScheme.surfaceContainer else MaterialTheme.colorScheme.surface,
                shadowElevation = 4.dp,
                border = bordeOscuro(),
            ) {
                SelectorHorario(vm.horario, vm::cambiarHorario, Modifier.padding(12.dp))
            }
            SmallFloatingActionButton(
                onClick = { if (tienePermisoDeUbicacion(context)) ubicarConGps() else pedirPermiso.launch(PERMISOS_UBICACION) },
                modifier = Modifier.align(Alignment.BottomEnd).padding(end = 12.dp, bottom = asomaHoja + 12.dp),
            ) { Icon(Icons.Filled.MyLocation, contentDescription = "Buscar cerca de mi ubicación") }
        }
    }
}

/** Contenido de la hoja: encabezado con la cantidad y la lista ordenada por distancia. */
@Composable
private fun HojaGarajes(
    vm: BuscarViewModel,
    lista: LazyListState,
    debajo: Dp,
    alElegir: (GarajeDisponible, Horario, Vehiculo?) -> Unit,
) {
    val lleno = vm.lleno
    Column(Modifier.fillMaxWidth().fillMaxHeight(0.75f)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                when {
                    lleno != null -> "${lleno.nombre} está lleno"
                    vm.cargando && vm.garajes.isEmpty() -> "Buscando garajes…"
                    vm.garajes.size == 1 -> "1 garaje cerca"
                    else -> "${vm.garajes.size} garajes cerca"
                },
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            if (vm.cargando) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            if (lleno != null) TextButton(onClick = vm::volverALaLista) { Text("Ver todos") }
        }
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
            when {
                lleno != null -> Box(Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                    .padding(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + debajo)) {
                    ListaCercanos("Estos garajes cercanos tienen lugar", vm.cercanos) { g ->
                        alElegir(g, vm.horario, vm.vehiculo)
                    }
                }
                vm.error != null -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(vm.error!!, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center,
                        modifier = Modifier.padding(24.dp))
                    TextButton(onClick = vm::buscar) { Text("Reintentar") }
                }
                vm.garajes.isEmpty() && !vm.cargando -> Text(
                    if (vm.horario.modalidad != "HORA") "Ningún garaje cercano ofrece este abono. Probá con otra modalidad."
                    else if (vm.posicion.esReal) "No hay garajes con Drivly a menos de 1 km de tu ubicación para ese horario."
                    else "No hay garajes con Drivly en esta zona para ese horario.",
                    textAlign = TextAlign.Center, modifier = Modifier.padding(24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> LazyColumn(
                    Modifier.fillMaxSize(),
                    state = lista,
                    contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + debajo),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(vm.garajes, key = { it.id }) { g ->
                        TarjetaGaraje(g, elegido = g.id == vm.elegido, precioExacto = vm.vehiculo != null,
                            onClick = { if (g.lugaresLibres > 0) alElegir(g, vm.horario, vm.vehiculo) else vm.verCercanos(g) })
                    }
                }
            }
        }
    }
}

@Composable
private fun TarjetaGaraje(g: GarajeDisponible, elegido: Boolean, precioExacto: Boolean, onClick: () -> Unit) {
    val lleno = g.lugaresLibres <= 0
    Tarjeta(
        Modifier.fillMaxWidth(),
        onClick = onClick,
        borde = if (elegido) BorderStroke(2.dp, MaterialTheme.colorScheme.primary) else null,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(g.nombre, style = MaterialTheme.typography.titleMedium)
                Text("${g.distanciaM} m", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(g.direccion, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                // Con vehículo el precio es el de su categoría; sin él, el más barato del garaje
                Text("${if (precioExacto) "" else "Desde "}${ars(g.precioDesde)} ${g.precioUnidad}",
                    style = MaterialTheme.typography.titleSmall)
                Text(
                    if (lleno) "Lleno · ver cercanos" else "${g.lugaresLibres} libres",
                    style = MaterialTheme.typography.labelLarge,
                    color = if (lleno) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

/** Chip con la patente del vehículo con el que se cotiza; si hay más de uno, abre un menú para cambiarlo. */
@Composable
private fun SelectorVehiculo(vehiculos: List<Vehiculo>, actual: Vehiculo?, alElegir: (Vehiculo) -> Unit) {
    if (actual == null) return
    var abierto by remember { mutableStateOf(false) }
    Box(Modifier.padding(end = 8.dp)) {
        AssistChip(
            onClick = { if (vehiculos.size > 1) abierto = true },
            label = { Text(actual.patente, fontFamily = JetBrainsMono) },
            leadingIcon = { Icon(Icons.Filled.DirectionsCar, null, Modifier.size(AssistChipDefaults.IconSize)) },
            trailingIcon = if (vehiculos.size > 1) ({ Icon(Icons.Filled.ArrowDropDown, null) }) else null,
        )
        DropdownMenu(expanded = abierto, onDismissRequest = { abierto = false }) {
            vehiculos.forEach { v ->
                DropdownMenuItem(
                    text = { Text("${v.patente} · ${v.categoria?.lowercase()?.replaceFirstChar { it.uppercase() } ?: ""}") },
                    onClick = { abierto = false; alElegir(v) },
                )
            }
        }
    }
}
