package com.drivly.app.ui.playero

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.ErrorDrivly
import com.drivly.app.data.api.AlertaOverstay
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.GarajeDisponible
import com.drivly.app.data.api.GarajeOperado
import com.drivly.app.data.api.Ocupacion
import com.drivly.app.data.api.PedidoEscaneo
import com.drivly.app.data.api.Reserva
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.hora
import com.drivly.app.ui.iso
import com.drivly.app.ui.theme.Action
import com.drivly.app.ui.theme.Brand
import com.drivly.app.ui.theme.BrandLight
import com.drivly.app.ui.theme.Debt
import com.drivly.app.ui.theme.DebtLight
import com.drivly.app.ui.theme.Hold
import com.drivly.app.ui.theme.Ink
import com.drivly.app.ui.theme.Ink700
import com.drivly.app.ui.theme.JetBrainsMono
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

enum class Modo { INGRESO, EGRESO, SIN_LUGAR }

enum class Nivel { VERDE, AMBAR, ROJO }

private val SALIDAS = listOf(60, 120, 240)
private val PATENTE = Regex("^([A-Z]{2}\\d{3}[A-Z]{2}|[A-Z]\\d{3}[A-Z]{3}|[A-Z]{3}\\d{3})$")
private val GRIS_PRESENCIAL = Color(0xFF7A8496)

fun limpiarPatente(texto: String): String = texto.replace(Regex("[\\s-]"), "").uppercase()

fun esPatente(texto: String): Boolean = PATENTE.matches(limpiarPatente(texto))

/** Rojo = no entra nadie más sin reserva sin dejar sin lugar a una reserva de la app. */
fun nivelPresencial(libresPresencial: Int, capacidad: Int): Nivel = when {
    libresPresencial <= 0 -> Nivel.ROJO
    capacidad > 0 && libresPresencial.toDouble() / capacidad <= 0.1 -> Nivel.AMBAR
    else -> Nivel.VERDE
}

fun horasLabel(minutos: Int): String = if (minutos % 60 == 0) "${minutos / 60} h" else "$minutos min"

data class Aviso(val ok: Boolean, val texto: String)

/** Regla 6: garajes a los que mandar a quien no entra. `cercanos` null = todavía se están buscando. */
data class Derivacion(val titulo: String, val detalle: String?, val cercanos: List<GarajeDisponible>?)

class PlayeroViewModel(private val api: DrivlyApi) : ViewModel() {
    var garaje by mutableStateOf<GarajeOperado?>(null)
        private set
    var sinGaraje by mutableStateOf(false)
        private set
    var errorCarga by mutableStateOf<String?>(null)
        private set
    var ocupacion by mutableStateOf<Ocupacion?>(null)
        private set
    var modo by mutableStateOf<Modo?>(null)
    var manual by mutableStateOf("")
    var salidaMin by mutableStateOf<Int?>(null)
    var ocupado by mutableStateOf(false)
        private set
    var aviso by mutableStateOf<Aviso?>(null)
        private set
    var derivacion by mutableStateOf<Derivacion?>(null)
    var cobro by mutableStateOf<CobroDeuda?>(null)
        private set
    val movimientos = mutableStateListOf<Reserva>()

    val ventana get() = salidaMin ?: ocupacion?.ventanaMin ?: 120
    val sinLugarPresencial get() = ocupacion?.let { it.libresPresencial <= 0 } == true
    val visorActivo get() = modo != null && !ocupado && cobro == null
    val salidas get() = (SALIDAS + (ocupacion?.ventanaMin ?: 120)).distinct().sorted()

    init {
        cargarGaraje()
    }

    fun cargarGaraje() {
        errorCarga = null
        sinGaraje = false
        viewModelScope.launch {
            try {
                val g = api.misGarajes().results.firstOrNull()
                garaje = g
                sinGaraje = g == null
            } catch (e: Exception) {
                errorCarga = e.comoErrorDrivly().message
            }
        }
    }

    /** Si falla una consulta del semáforo se mantiene el último dato: se reintenta a los 10 s. */
    suspend fun actualizarOcupacion() {
        val g = garaje ?: return
        runCatching { api.ocupacion(g.id) }.onSuccess { ocupacion = it }
    }

    fun alEscanear(token: String) = procesar(qr = token, patente = null, desdeCamara = true)

    fun enviarManual() {
        val texto = manual.trim()
        if (texto.isEmpty()) return
        if (modo == Modo.SIN_LUGAR || !esPatente(texto)) procesar(qr = texto, patente = null, desdeCamara = false)
        else procesar(qr = null, patente = limpiarPatente(texto), desdeCamara = false)
    }

    private fun procesar(qr: String?, patente: String?, desdeCamara: Boolean) {
        val modoActual = modo ?: return
        val g = garaje ?: return
        if (ocupado) return
        aviso = null
        derivacion = null

        // Cliente sin reserva con el semáforo en rojo: no se registra, se deriva (regla 6)
        if (modoActual == Modo.INGRESO && patente != null && sinLugarPresencial) {
            mostrarCercanos(g, TITULO_SIN_LUGAR,
                "Los lugares libres están comprometidos con conductores de la app. Indicale un garaje cercano:", null)
            return
        }

        ocupado = true
        viewModelScope.launch {
            try {
                when (modoActual) {
                    Modo.SIN_LUGAR -> sinLugar(g, qr)
                    Modo.INGRESO, Modo.EGRESO -> ingresoOEgreso(g, modoActual, qr, patente)
                }
                modo = null
                manual = ""
                salidaMin = null
            } catch (e: Exception) {
                val error = e.comoErrorDrivly()
                mostrarError(g, error)
                // Con el visor encendido el mismo QR se volvería a leer sin parar
                if (desdeCamara || error.deuda != null) modo = null
            } finally {
                ocupado = false
            }
        }
    }

    private suspend fun sinLugar(g: GarajeOperado, qr: String?) {
        val r = api.sinLugar(PedidoEscaneo(g.id, qrToken = qr))
        registrar(r.reserva)
        mostrarCercanos(
            g,
            "Reserva de ${r.reserva.patente} marcada sin lugar",
            "Se pidió el reembolso de ${ars(r.reembolso.monto)} y el incidente quedó registrado. Indicale al conductor un garaje cercano:",
            r.cercanos,
        )
    }

    private suspend fun ingresoOEgreso(g: GarajeOperado, modoActual: Modo, qr: String?, patente: String?) {
        val salida = if (patente != null && modoActual == Modo.INGRESO) OffsetDateTime.now().plusMinutes(ventana.toLong()).iso() else null
        val pedido = PedidoEscaneo(g.id, qr, patente, salida)
        val r = if (modoActual == Modo.INGRESO) api.ingreso(pedido) else api.egreso(pedido)
        registrar(r.reserva)
        when {
            r.deuda != null -> cobro = CobroDeuda(r.deuda, antesDeIngreso = false)
            modoActual == Modo.EGRESO && r.reserva.origen == "PRESENCIAL" ->
                aviso = Aviso(true, "Egreso registrado. Cobrar ${ars(r.reserva.total)}.")
            modoActual == Modo.INGRESO -> aviso = Aviso(true, "Ingreso registrado. Barrera abierta.")
            else -> aviso = Aviso(true, "Egreso registrado. Salida liberada.")
        }
        if (r.ocupacion != null) ocupacion = r.ocupacion else actualizarOcupacion()
    }

    private suspend fun mostrarError(g: GarajeOperado, error: ErrorDrivly) {
        when {
            error.codigo == "DEUDA_PATENTE" && error.deuda != null -> cobro = CobroDeuda(error.deuda, antesDeIngreso = true)
            error.codigo == "SIN_LUGAR_PRESENCIAL" -> {
                mostrarCercanos(g, TITULO_SIN_LUGAR, error.message, error.cercanos)
                actualizarOcupacion()
            }
            else -> aviso = Aviso(false, error.message.orEmpty())
        }
    }

    private fun registrar(reserva: Reserva) {
        movimientos.removeAll { it.id == reserva.id }
        movimientos.add(0, reserva)
        while (movimientos.size > 4) movimientos.removeAt(movimientos.lastIndex)
    }

    private fun mostrarCercanos(g: GarajeOperado, titulo: String, detalle: String?, cercanos: List<GarajeDisponible>?) {
        derivacion = Derivacion(titulo, detalle, cercanos)
        if (cercanos != null) return
        viewModelScope.launch {
            val encontrados = runCatching { api.cercanos(g.id) }.getOrDefault(emptyList())
            derivacion = derivacion?.copy(cercanos = encontrados)
        }
    }

    fun deudaCobrada() {
        val c = cobro ?: return
        cobro = null
        movimientos.replaceAll { if (it.id == c.deuda.reservaId) it.copy(estado = "FINALIZADA") else it }
        aviso = Aviso(true, if (c.antesDeIngreso) "Deuda saldada. Volvé a escanear para registrar el ingreso." else "Deuda saldada. Salida liberada.")
        viewModelScope.launch { actualizarOcupacion() }
    }

    fun sigueConDeuda() {
        val c = cobro ?: return
        cobro = null
        aviso = Aviso(false,
            if (c.antesDeIngreso) "No se registró el ingreso: la deuda sigue pendiente."
            else "Salió con deuda de ${ars(c.deuda.total)}. La cuenta queda bloqueada hasta saldarla.")
        viewModelScope.launch { actualizarOcupacion() }
    }

    private companion object {
        const val TITULO_SIN_LUGAR = "Sin lugar para clientes sin reserva"
    }
}

/** Operación del garaje, igual que ValetPortalView.jsx: semáforo, escaneo, deudas y derivación a cercanos. */
@Composable
fun PlayeroScreen(alAbrirPerfil: () -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val vm: PlayeroViewModel = viewModel { PlayeroViewModel(app.api) }
    val nombre by app.sesion.nombre.collectAsStateWithLifecycle(initialValue = "")
    val ciclo = LocalLifecycleOwner.current.lifecycle
    val garajeId = vm.garaje?.id

    LaunchedEffect(garajeId, ciclo) {
        if (garajeId == null) return@LaunchedEffect
        ciclo.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                vm.actualizarOcupacion()
                delay(10_000)
            }
        }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Encabezado(vm.garaje?.nombre, nombre, alAbrirPerfil)
            when {
                vm.sinGaraje -> AvisoCarga(
                    "No tenés un garaje asignado",
                    "Pedile al administrador que te agregue desde Equipo (Playeros).",
                    vm::cargarGaraje,
                )
                vm.errorCarga != null -> AvisoCarga("No se pudo cargar tu garaje", vm.errorCarga.orEmpty(), vm::cargarGaraje)
                else -> Operacion(vm)
            }
        }
    }

    vm.cobro?.let { DialogoDeuda(it, app.api, alCobrar = vm::deudaCobrada, alSeguirConDeuda = vm::sigueConDeuda) }
}

@Composable
private fun Encabezado(garaje: String?, nombre: String, alAbrirPerfil: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(garaje ?: "…", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold,
                maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("Operador · ${nombre.ifBlank { "Playero" }}", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Box(
            Modifier.size(48.dp).background(MaterialTheme.colorScheme.surfaceContainerHigh, CircleShape)
                .clickable(onClickLabel = "Abrir perfil", onClick = alAbrirPerfil),
            contentAlignment = Alignment.Center,
        ) {
            Text(nombre.ifBlank { "P" }.take(2).uppercase(), fontWeight = FontWeight.ExtraBold)
        }
    }
}

@Composable
private fun AvisoCarga(titulo: String, detalle: String, alReintentar: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(titulo, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
        Text(detalle, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedButton(onClick = alReintentar) { Text("Reintentar") }
    }
}

/** Una columna en el teléfono y dos en la tablet, como el portal web. */
@Composable
private fun Operacion(vm: PlayeroViewModel) {
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (maxWidth >= 600.dp) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) { Lectura(vm) }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) { Acciones(vm) }
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Lectura(vm)
                Acciones(vm)
            }
        }
    }
}

@Composable
private fun Lectura(vm: PlayeroViewModel) {
    Semaforo(vm.ocupacion)
    VisorQr(activo = vm.visorActivo, alEscanear = vm::alEscanear)
}

@Composable
private fun Acciones(vm: PlayeroViewModel) {
    val modo = vm.modo
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        BotonEscanear("Ingreso", modo == Modo.INGRESO, Action, Ink, Modifier.weight(1f)) { vm.modo = Modo.INGRESO }
        BotonEscanear("Egreso", modo == Modo.EGRESO, Brand, Color.White, Modifier.weight(1f)) { vm.modo = Modo.EGRESO }
    }
    OutlinedButton(onClick = { vm.modo = Modo.SIN_LUGAR }, modifier = Modifier.fillMaxWidth().height(48.dp)) {
        Text("Llegó con reserva y no hay lugar físico", color = if (modo == Modo.SIN_LUGAR) DebtLight else MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
    if (modo == Modo.SIN_LUGAR) {
        Text("Escaneá su QR: se reembolsa la reserva y le ofrecés un garaje cercano.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = vm.manual, onValueChange = { vm.manual = it },
            placeholder = { Text("Patente o código manual") }, singleLine = true,
            textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = JetBrainsMono),
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { if (modo != null) vm.enviarManual() }),
            modifier = Modifier.weight(1f),
        )
        FilledTonalButton(onClick = vm::enviarManual, enabled = modo != null && !vm.ocupado && vm.manual.isNotBlank(),
            modifier = Modifier.height(56.dp)) {
            Text(if (vm.ocupado) "…" else "OK")
        }
    }

    if (modo == Modo.INGRESO && esPatente(vm.manual)) SalidaEstimada(vm)
    AlertasOverstay(vm.ocupacion?.alertasOverstay.orEmpty())
    vm.derivacion?.let { d -> Derivar(d, alCerrar = { vm.derivacion = null }) }
    vm.aviso?.let { AvisoOperacion(it) }
    Movimientos(vm.movimientos)
}

@Composable
private fun BotonEscanear(titulo: String, elegido: Boolean, fondo: Color, texto: Color, modifier: Modifier, alElegir: () -> Unit) {
    val colores = if (elegido) ButtonDefaults.buttonColors(containerColor = fondo, contentColor = texto)
    else ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh, contentColor = MaterialTheme.colorScheme.onSurface)
    Button(onClick = alElegir, colors = colores, shape = MaterialTheme.shapes.large, modifier = modifier.height(76.dp)
        .semantics { contentDescription = "Escanear $titulo" + if (elegido) ", elegido" else "" }) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Escanear", style = MaterialTheme.typography.labelLarge)
            Text(titulo, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
        }
    }
}

@Composable
private fun SalidaEstimada(vm: PlayeroViewModel) {
    Column(
        Modifier.fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.outlineVariant, MaterialTheme.shapes.medium).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Cliente sin reserva · ¿cuánto se queda?", fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            vm.salidas.forEach { m ->
                val elegida = vm.ventana == m
                Button(
                    onClick = { vm.salidaMin = m },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (elegida) Brand else MaterialTheme.colorScheme.surfaceContainerHigh,
                        contentColor = if (elegida) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                    modifier = Modifier.weight(1f).height(48.dp),
                ) { Text(horasLabel(m), maxLines = 1) }
            }
        }
        if (vm.sinLugarPresencial) {
            Text("El semáforo está en rojo: este cliente no puede entrar sin chocar con reservas.",
                style = MaterialTheme.typography.bodySmall, color = DebtLight, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Semaforo(o: Ocupacion?) {
    val forma = MaterialTheme.shapes.large
    val fondo = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerLow, forma)
        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, forma)
    if (o == null) {
        Box(fondo.height(120.dp))
        return
    }
    val nivel = nivelPresencial(o.libresPresencial, o.capacidad)
    val color = when (nivel) {
        Nivel.VERDE -> Action
        Nivel.AMBAR -> Hold
        Nivel.ROJO -> Debt
    }
    val ocupadosApp = o.ocupadosApp + o.ocupadosAbonos
    Row(
        fondo.padding(16.dp).semantics {
            contentDescription = "${o.libresPresencial} lugares para clientes sin reserva, ${o.libres} libres de ${o.capacidad}"
        },
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.background(Color(0xFF0B0F17), MaterialTheme.shapes.medium).padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(Nivel.ROJO to Debt, Nivel.AMBAR to Hold, Nivel.VERDE to Action).forEach { (n, c) ->
                Box(Modifier.size(24.dp).background(if (n == nivel) c else Color(0xFF2A3446), CircleShape))
            }
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("${o.libresPresencial}", style = MaterialTheme.typography.displaySmall, color = color, fontWeight = FontWeight.ExtraBold)
                Text(if (nivel == Nivel.ROJO) "sin lugar para clientes sin reserva" else "lugares para clientes sin reserva",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            BarraOcupacion(o, ocupadosApp)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Referencia(Brand, "App y abonos $ocupadosApp")
                Referencia(GRIS_PRESENCIAL, "Presencial ${o.ocupadosPresencial}")
                Referencia(BrandLight, "Llegan en ${horasLabel(o.ventanaMin)}: ${o.proximasApp}")
                Text("${o.libres} libres de ${o.capacidad}", style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun BarraOcupacion(o: Ocupacion, ocupadosApp: Int) {
    val partes = listOf(
        Brand to ocupadosApp,
        GRIS_PRESENCIAL to o.ocupadosPresencial,
        BrandLight to minOf(o.proximasApp, o.libres),
    ).filter { it.second > 0 }
    val resto = o.capacidad - partes.sumOf { it.second }
    Row(Modifier.fillMaxWidth().height(10.dp).background(Ink700, CircleShape), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        partes.forEach { (color, cantidad) ->
            Box(Modifier.weight(cantidad.toFloat()).fillMaxHeight().background(color, MaterialTheme.shapes.extraSmall))
        }
        if (resto > 0) Spacer(Modifier.weight(resto.toFloat()))
    }
}

@Composable
private fun Referencia(color: Color, texto: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(color, MaterialTheme.shapes.extraSmall))
        Text(texto, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** RFW-16: un overstay deja sin lugar a una reserva próxima. */
@Composable
private fun AlertasOverstay(alertas: List<AlertaOverstay>) {
    if (alertas.isEmpty()) return
    Column(
        Modifier.fillMaxWidth().background(Debt.copy(alpha = 0.15f), MaterialTheme.shapes.medium).padding(12.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text("Un vehículo excedido deja sin lugar a ${if (alertas.size == 1) "una reserva" else "${alertas.size} reservas"}:",
            color = DebtLight, fontWeight = FontWeight.Bold)
        alertas.forEach {
            Text("${it.patente} · llega ${hora(it.inicio)}", color = DebtLight, fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyMedium.copy(fontFamily = JetBrainsMono))
        }
    }
}

@Composable
private fun Derivar(d: Derivacion, alCerrar: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        d.detalle?.let { AvisoOperacion(Aviso(false, it)) }
        Column(
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerLow, MaterialTheme.shapes.large).padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(d.titulo, fontWeight = FontWeight.ExtraBold)
            val cercanos = d.cercanos
            when {
                cercanos == null -> Text("Buscando garajes con lugar…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                cercanos.isEmpty() -> Text("No hay garajes Drivly con lugar en 1 km. Probá con otro horario.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                else -> cercanos.forEach { GarajeCercano(it) }
            }
        }
        TextButton(onClick = alCerrar, modifier = Modifier.align(Alignment.End)) { Text("Cerrar") }
    }
}

@Composable
private fun GarajeCercano(g: GarajeDisponible) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(g.nombre, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${g.direccion} · a ${g.distanciaM} m", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text("${g.lugaresLibres} libres", color = Action, fontWeight = FontWeight.ExtraBold)
            Text("desde ${ars(g.precioDesde)} ${g.precioUnidad}", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun AvisoOperacion(aviso: Aviso) {
    val color = if (aviso.ok) Action else DebtLight
    Text(
        aviso.texto, color = color, fontWeight = FontWeight.Bold,
        modifier = Modifier.fillMaxWidth().background(color.copy(alpha = 0.15f), MaterialTheme.shapes.medium).padding(12.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
    )
}

@Composable
private fun Movimientos(movimientos: List<Reserva>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("ÚLTIMOS MOVIMIENTOS", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (movimientos.isEmpty()) {
            Text("Todavía no hay movimientos en este turno.", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        movimientos.forEach { r ->
            val app = r.origen == "APP"
            Row(
                Modifier.fillMaxWidth().height(48.dp)
                    .background(MaterialTheme.colorScheme.surfaceContainerLow, MaterialTheme.shapes.medium).padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(r.patente, style = MaterialTheme.typography.bodyMedium.copy(fontFamily = JetBrainsMono), fontWeight = FontWeight.Bold)
                Text(
                    when {
                        !app -> "Sin reserva"
                        r.modalidad != "HORA" -> "Abono"
                        else -> "App"
                    },
                    style = MaterialTheme.typography.labelSmall, color = if (app) BrandLight else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                EstadoChip(r.estado)
            }
        }
    }
}
