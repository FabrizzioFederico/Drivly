package com.drivly.app.ui.playero

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.drivly.app.data.api.CierreCaja
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoCierre
import com.drivly.app.data.api.ResumenCaja
import com.drivly.app.data.api.TotalMedio
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.ui.ars
import com.drivly.app.ui.hora
import com.drivly.app.ui.theme.Action
import com.drivly.app.ui.theme.Debt
import kotlinx.coroutines.launch
import java.math.BigDecimal

/** Los medios con que se cobra a un cliente sin reserva, en el orden en que se muestran. */
val MEDIOS_PRESENCIAL = listOf("EFECTIVO" to "Efectivo", "MERCADO_PAGO" to "Mercado Pago", "TRANSFERENCIA" to "Transferencia")

/** Salida de un cliente sin reserva: el playero marca con qué le pagó. Cerrar sin elegir lo deja "sin indicar". */
@Composable
fun DialogoMedioPresencial(patente: String, total: String, alElegir: (String) -> Unit, alCerrar: () -> Unit) {
    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("Cobrá ${ars(total)}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Salida de $patente. ¿Cómo te pagó?", color = MaterialTheme.colorScheme.onSurfaceVariant)
                MEDIOS_PRESENCIAL.forEach { (medio, texto) ->
                    val principal = medio == "EFECTIVO"
                    val modificador = Modifier.fillMaxWidth().height(52.dp)
                    if (principal) Button(onClick = { alElegir(medio) }, modifier = modificador) { Text(texto) }
                    else OutlinedButton(onClick = { alElegir(medio) }, modifier = modificador) { Text(texto) }
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = alCerrar) { Text("Después") } },
    )
}

private fun total(medios: Map<String, TotalMedio>, vararg claves: String) =
    claves.sumOf { BigDecimal(medios[it]?.total ?: "0") }

private fun cantidad(medios: Map<String, TotalMedio>, vararg claves: String) = claves.sumOf { medios[it]?.cantidad ?: 0 }

/**
 * Cierre de caja del día: muestra cuánto efectivo debería haber desde el último cierre, el playero carga lo que
 * contó y queda registrada la diferencia (el admin la ve en el panel web).
 */
@Composable
fun DialogoCaja(api: DrivlyApi, garajeId: String, alCerrar: () -> Unit) {
    val alcance = rememberCoroutineScope()
    var resumen by remember { mutableStateOf<ResumenCaja?>(null) }
    var cierre by remember { mutableStateOf<CierreCaja?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var contado by remember { mutableStateOf("") }
    var observaciones by remember { mutableStateOf("") }
    var enviando by remember { mutableStateOf(false) }

    LaunchedEffect(garajeId) {
        runCatching { api.caja(garajeId) }.onSuccess { resumen = it }.onFailure { error = it.comoErrorDrivly().message }
    }
    val monto = contado.replace(".", "").replace(',', '.').toBigDecimalOrNull()

    AlertDialog(
        onDismissRequest = { if (!enviando) alCerrar() },
        title = { Text(if (cierre != null) "Caja cerrada" else "Cerrar caja del día") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                val hecho = cierre
                val r = resumen
                when {
                    hecho != null -> ResultadoCierre(hecho)
                    r == null && error == null -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
                    r != null -> {
                        Text("Desde ${if (r.ultimoCierre != null) "el último cierre, a las ${hora(r.desde)}" else "el comienzo del día"}",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Fila("Clientes sin reserva en efectivo (${cantidad(r.presenciales, "EFECTIVO", "SIN_INDICAR")})",
                            total(r.presenciales, "EFECTIVO", "SIN_INDICAR"))
                        Fila("Excesos cobrados en efectivo (${cantidad(r.excesos, "EFECTIVO")})", total(r.excesos, "EFECTIVO"))
                        HorizontalDivider()
                        Fila("Efectivo que tiene que haber", BigDecimal(r.efectivoEsperado), destacado = true)
                        if ((r.presenciales["SIN_INDICAR"]?.cantidad ?: 0) > 0) {
                            Text("${r.presenciales["SIN_INDICAR"]?.cantidad} cobro(s) sin medio marcado se cuentan como efectivo.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("Por otros medios (no van a la caja): Mercado Pago ${ars(total(r.presenciales, "MERCADO_PAGO").plus(total(r.excesos, "MERCADO_PAGO")).toPlainString())} · " +
                            "transferencias ${ars(total(r.presenciales, "TRANSFERENCIA").toPlainString())}",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedTextField(
                            value = contado, onValueChange = { nuevo -> contado = nuevo.filter { it.isDigit() || it == ',' } },
                            label = { Text("Efectivo que contaste") }, prefix = { Text("$ ") }, singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        OutlinedTextField(
                            value = observaciones, onValueChange = { observaciones = it.take(1000) },
                            label = { Text("Observaciones (opcional)") }, modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            if (cierre != null) {
                Button(onClick = alCerrar) { Text("Listo") }
            } else if (resumen != null) {
                Button(
                    enabled = monto != null && !enviando,
                    onClick = {
                        enviando = true
                        error = null
                        alcance.launch {
                            runCatching { api.cerrarCaja(PedidoCierre(garajeId, monto!!.toPlainString(), observaciones.trim())) }
                                .onSuccess { cierre = it }
                                .onFailure { error = it.comoErrorDrivly().message }
                            enviando = false
                        }
                    },
                ) { Text(if (enviando) "Cerrando…" else "Cerrar caja") }
            }
        },
        dismissButton = { if (cierre == null) TextButton(onClick = alCerrar, enabled = !enviando) { Text("Cancelar") } },
    )
}

@Composable
private fun Fila(texto: String, valor: BigDecimal, destacado: Boolean = false) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(texto, Modifier.weight(1f), style = if (destacado) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyMedium,
            fontWeight = if (destacado) FontWeight.Bold else FontWeight.Normal)
        Text(ars(valor.toPlainString()), fontWeight = if (destacado) FontWeight.ExtraBold else FontWeight.SemiBold)
    }
}

@Composable
private fun ResultadoCierre(c: CierreCaja) {
    val diferencia = BigDecimal(c.diferencia)
    val (texto, color) = when (diferencia.signum()) {
        0 -> "La caja cierra justa." to Action
        -1 -> "Faltan ${ars(diferencia.negate().toPlainString())}." to Debt
        else -> "Sobran ${ars(c.diferencia)}." to MaterialTheme.colorScheme.primary
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(texto, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold, color = color)
        Fila("Tenía que haber", BigDecimal(c.efectivoEsperado))
        Fila("Contaste", BigDecimal(c.efectivoContado))
        Text("El cierre quedó registrado y el administrador lo ve en el panel.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
