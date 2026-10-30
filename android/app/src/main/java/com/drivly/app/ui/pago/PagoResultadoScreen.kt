package com.drivly.app.ui.pago

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.comoErrorDrivly
import kotlinx.coroutines.delay

/**
 * Destino del deep link drivly://pago-resultado. Los parámetros del deep link no se toman como verdad:
 * se consulta la reserva cada 2 s hasta que el webhook de Mercado Pago la confirme en el servidor.
 */
@Composable
fun PagoResultadoScreen(reservaId: String, estadoMp: String?, alConfirmar: (String) -> Unit, alVolver: () -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val aprobado = estadoMp == "approved" || estadoMp == "success"
    val pendiente = estadoMp == "pending" || estadoMp == "in_process"
    var mensaje by remember {
        mutableStateOf(
            when {
                aprobado -> "Pago aprobado. Confirmando tu reserva…"
                pendiente -> "Tu pago está pendiente de acreditación. La reserva se confirma cuando Mercado Pago lo apruebe."
                else -> "El pago no se completó. Podés volver a intentarlo mientras el lugar siga retenido."
            }
        )
    }
    var esperando by remember { mutableStateOf(aprobado) }

    LaunchedEffect(reservaId) {
        if (!aprobado) return@LaunchedEffect
        repeat(15) {
            try {
                val r = app.api.reserva(reservaId)
                when (r.estado) {
                    "CONFIRMADA", "EN_CURSO" -> return@LaunchedEffect alConfirmar(reservaId)
                    "HOLD" -> Unit
                    else -> {
                        mensaje = "No pudimos confirmar la reserva porque el lugar ya no estaba disponible. El reembolso es automático."
                        esperando = false
                        return@LaunchedEffect
                    }
                }
            } catch (e: Exception) {
                mensaje = e.comoErrorDrivly().message ?: mensaje
            }
            delay(2000)
        }
        mensaje = "Tu pago se está procesando. Revisá la reserva en unos minutos."
        esperando = false
    }

    PantallaResultado(esperando, mensaje, alVolver)
}

/** Igual que con una reserva: la deuda se da por saldada recién cuando el webhook lo confirma en el servidor. */
@Composable
fun PagoDeudaResultadoScreen(reservaId: String, estadoMp: String?, alVolver: () -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val aprobado = estadoMp == "approved" || estadoMp == "success"
    val pendiente = estadoMp == "pending" || estadoMp == "in_process"
    var mensaje by remember {
        mutableStateOf(
            when {
                aprobado -> "Pago aprobado. Saldando tu deuda…"
                pendiente -> "Tu pago está pendiente de acreditación. La deuda se salda cuando Mercado Pago lo apruebe."
                else -> "El pago no se completó. La deuda sigue pendiente: podés volver a intentarlo desde Mis reservas."
            }
        )
    }
    var esperando by remember { mutableStateOf(aprobado) }

    LaunchedEffect(reservaId) {
        if (!aprobado) return@LaunchedEffect
        repeat(15) {
            try {
                if (app.api.misDeudas().none { it.reservaId == reservaId }) {
                    mensaje = "Deuda saldada. Ya podés volver a reservar."
                    esperando = false
                    return@LaunchedEffect
                }
            } catch (e: Exception) {
                mensaje = e.comoErrorDrivly().message ?: mensaje
            }
            delay(2000)
        }
        mensaje = "Tu pago se está procesando. Revisá Mis reservas en unos minutos."
        esperando = false
    }

    PantallaResultado(esperando, mensaje, alVolver)
}

@Composable
private fun PantallaResultado(esperando: Boolean, mensaje: String, alVolver: () -> Unit) {
    Scaffold { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (esperando) CircularProgressIndicator()
            Text(mensaje, style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            if (!esperando) {
                Button(onClick = alVolver, modifier = Modifier.fillMaxWidth().height(56.dp)) { Text("Volver") }
            }
        }
    }
}
