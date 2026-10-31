package com.drivly.app.ui.playero

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.drivly.app.data.api.Deuda
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.hora
import com.drivly.app.ui.theme.Action
import com.drivly.app.ui.theme.DebtLight
import com.drivly.app.ui.theme.Ink
import com.drivly.app.ui.theme.JetBrainsMono
import com.drivly.app.ui.ticket.generarQr
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.math.RoundingMode

/** Deuda a cobrar. `antesDeIngreso`: es de una estadía anterior y frena el ingreso de la patente (CP-30). */
data class CobroDeuda(val deuda: Deuda, val antesDeIngreso: Boolean)

private data class Pagado(val medio: String, val transaccion: String? = null)

/** CU-08. Sólo se cierra con una decisión del playero: tocar afuera no puede perder el cobro. */
@Composable
fun DialogoDeuda(cobro: CobroDeuda, api: DrivlyApi, alCobrar: () -> Unit, alSeguirConDeuda: () -> Unit) {
    val d = cobro.deuda
    val alcance = rememberCoroutineScope()
    var pagado by remember { mutableStateOf<Pagado?>(null) }
    var ocupado by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun verificar() = alcance.launch {
        error = null
        try {
            val r = api.estadoDeuda(d.reservaId)
            if (r.pagado) pagado = Pagado("Mercado Pago", r.transaccionId)
        } catch (e: Exception) {
            error = e.comoErrorDrivly().message
        }
    }

    // El webhook de Mercado Pago salda la deuda en el servidor: se consulta cada 3 s
    LaunchedEffect(pagado) {
        while (pagado == null) {
            delay(3000)
            runCatching { api.estadoDeuda(d.reservaId) }.getOrNull()?.takeIf { it.pagado }?.let {
                pagado = Pagado("Mercado Pago", it.transaccionId)
            }
        }
    }

    Dialog(
        onDismissRequest = {},
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false),
    ) {
        Surface(shape = MaterialTheme.shapes.extraLarge, color = MaterialTheme.colorScheme.surfaceContainer,
            modifier = Modifier.widthIn(max = 420.dp)) {
            Column(
                Modifier.verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    EstadoChip("CON_DEUDA")
                    Text(d.patente, style = MaterialTheme.typography.titleMedium.copy(fontFamily = JetBrainsMono))
                }
                if (cobro.antesDeIngreso) {
                    Text("Deuda impaga en ${d.garajeNombre}: hay que cobrarla antes del ingreso.",
                        color = DebtLight, fontWeight = FontWeight.Bold)
                }
                Text("Estadía excedida", style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("+${d.minutosExcedidos} min", style = MaterialTheme.typography.displaySmall,
                    color = DebtLight, fontWeight = FontWeight.ExtraBold)
                Row(Modifier.fillMaxWidth()) {
                    Dato("Reserva hasta", d.finReservado?.let(::hora) ?: "—", Modifier.weight(1f))
                    Dato("Tolerancia", "+${d.toleranciaMin} min", Modifier.weight(1f))
                    Dato("Egreso real", hora(d.egresoReal), Modifier.weight(1f))
                }
                Calculo(d)

                val p = pagado
                if (p == null) {
                    if (d.mpQrData.isNotBlank()) {
                        QrDeCobro(d)
                    } else {
                        Text(
                            if (d.efectivo) "El cobro por Mercado Pago no está disponible. Podés cobrar en efectivo."
                            else "El cobro por Mercado Pago no está disponible. El conductor puede pagarla desde su app o en ${d.garajeNombre}.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    error?.let { Text(it, color = DebtLight, fontWeight = FontWeight.Bold) }
                    if (!d.efectivo) {
                        Text("La deuda es de ${d.garajeNombre}: desde este garaje sólo se cobra por QR, que se le acredita a ese garaje.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        if (d.efectivo) {
                            OutlinedButton(
                                enabled = !ocupado,
                                onClick = {
                                    ocupado = true
                                    error = null
                                    alcance.launch {
                                        try {
                                            api.cobrarEnEfectivo(d.reservaId)
                                            pagado = Pagado("Efectivo")
                                        } catch (e: Exception) {
                                            error = e.comoErrorDrivly().message
                                        } finally {
                                            ocupado = false
                                        }
                                    }
                                },
                                modifier = Modifier.weight(1f).height(64.dp),
                            ) { Text("Cobro en efectivo") }
                        }
                        if (d.mpQrData.isNotBlank()) {
                            Button(onClick = { verificar() }, modifier = Modifier.weight(1f).height(64.dp)) {
                                Text("Verificar pago")
                            }
                        }
                    }
                    // Regla 4: Drivly no indica retener el vehículo. La deuda queda en la cuenta y bloquea nuevas reservas.
                    TextButton(onClick = alSeguirConDeuda, modifier = Modifier.fillMaxWidth()) {
                        Text(if (cobro.antesDeIngreso) "No ingresa" else "Salida con deuda")
                    }
                } else {
                    Column(
                        Modifier.fillMaxWidth().background(Action.copy(alpha = 0.12f), MaterialTheme.shapes.medium)
                            .padding(vertical = 20.dp, horizontal = 12.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text("PAGO ACREDITADO", color = Action, fontWeight = FontWeight.ExtraBold)
                        Text("${ars(d.total)} · ${p.medio}", style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.ExtraBold)
                        p.transaccion?.let {
                            Text("TX $it", style = MaterialTheme.typography.bodySmall.copy(fontFamily = JetBrainsMono),
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    Button(
                        onClick = alCobrar,
                        colors = ButtonDefaults.buttonColors(containerColor = Action, contentColor = Ink),
                        modifier = Modifier.fillMaxWidth().height(72.dp),
                    ) { Text(if (cobro.antesDeIngreso) "Continuar" else "Liberar salida") }
                }
            }
        }
    }
}

@Composable
private fun Dato(titulo: String, valor: String, modifier: Modifier) {
    Column(modifier) {
        Text(titulo, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(valor, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun Calculo(d: Deuda) {
    val estilo = MaterialTheme.typography.bodySmall.copy(fontFamily = JetBrainsMono)
    val secundario = MaterialTheme.colorScheme.onSurfaceVariant
    val recargo = BigDecimal(d.recargo).multiply(BigDecimal(100)).setScale(0, RoundingMode.HALF_UP)
    Column(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background, MaterialTheme.shapes.medium).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text("⌈${d.minutosExcedidos} min ÷ ${d.fraccionMin}⌉ = ${d.fracciones} fracciones", style = estilo, color = secundario)
        Text("${d.fracciones} × ${ars(d.precioFraccion)} + $recargo % de recargo", style = estilo, color = secundario)
        if (BigDecimal(d.montoCondonado).signum() > 0) {
            Text("Condonado por el garaje: −${ars(d.montoCondonado)}", style = estilo, color = secundario)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Text("Total a cobrar", style = estilo, fontWeight = FontWeight.Bold)
            Text(ars(d.total), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun QrDeCobro(d: Deuda) {
    val imagen = remember(d.mpQrData) { generarQr(d.mpQrData, 512) }
    // Fondo blanco siempre: los lectores necesitan contraste
    Row(
        Modifier.fillMaxWidth().background(Color.White, MaterialTheme.shapes.medium).padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(124.dp)) {
            Image(imagen.asImageBitmap(), contentDescription = "QR de Mercado Pago", Modifier.size(124.dp))
        }
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("QR Mercado Pago", color = Ink, fontWeight = FontWeight.ExtraBold)
            Text("El conductor escanea y paga ${ars(d.total)} desde su app.", color = Ink,
                style = MaterialTheme.typography.bodySmall)
            Text("Esperando pago…", color = Ink, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
        }
    }
}
