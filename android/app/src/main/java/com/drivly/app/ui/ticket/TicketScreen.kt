package com.drivly.app.ui.ticket

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.drivly.app.DrivlyApplication
import com.drivly.app.ui.components.Tarjeta
import com.drivly.app.data.api.Qr
import com.drivly.app.data.api.Reserva
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.data.json
import com.drivly.app.ui.ars
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.fechaHora
import com.drivly.app.ui.hora
import com.drivly.app.ui.theme.JetBrainsMono
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

/** El QR es estático y firmado: se descarga una vez y queda guardado para mostrarlo sin señal (RFM-09). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TicketScreen(reservaId: String, alVolver: (mensaje: String?) -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val alcance = rememberCoroutineScope()
    var reserva by remember { mutableStateOf<Reserva?>(null) }
    var qr by remember { mutableStateOf<Qr?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirmarCancelacion by remember { mutableStateOf(false) }
    var cancelando by remember { mutableStateOf(false) }

    LaunchedEffect(reservaId) {
        app.sesion.qrGuardado(reservaId)?.let { qr = json.decodeFromString(Qr.serializer(), it) }
        try {
            reserva = app.api.reserva(reservaId)
            if (qr == null) {
                val descargado = app.api.qr(reservaId)
                app.sesion.guardarQr(reservaId, json.encodeToString(Qr.serializer(), descargado))
                qr = descargado
            }
        } catch (e: Exception) {
            if (qr == null) error = e.comoErrorDrivly().message // con QR guardado alcanza aunque no haya señal
        }
    }

    val r = reserva
    val cancelable = r?.cancelableHasta?.let { OffsetDateTime.now().isBefore(OffsetDateTime.parse(it)) } == true

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mi ticket") },
                navigationIcon = {
                    IconButton(onClick = { alVolver(null) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Tarjeta(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically) {
                        Text("QR de ingreso y egreso", style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        r?.let { EstadoChip(it.estado) }
                    }
                    val token = qr?.qrToken
                    if (token != null) {
                        val imagen = remember(token) { generarQr(token, 640) }
                        // Fondo blanco siempre, también en modo oscuro: los lectores necesitan contraste
                        Box(Modifier.background(androidx.compose.ui.graphics.Color.White).padding(12.dp)) {
                            Image(imagen.asImageBitmap(), contentDescription = "Código QR de la reserva", Modifier.size(240.dp))
                        }
                        Text("Funciona sin señal. Mostralo al entrar y al salir.", style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else if (error == null) {
                        CircularProgressIndicator()
                    }
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            }

            if (r != null) {
                Tarjeta(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(r.patente, style = MaterialTheme.typography.headlineSmall.copy(fontFamily = JetBrainsMono))
                        Text("${fechaHora(r.inicio)} a ${hora(r.fin)}", style = MaterialTheme.typography.titleMedium)
                        r.garaje?.let {
                            Text(it.nombre, style = MaterialTheme.typography.titleMedium)
                            Text(it.direccion, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("Pagado: ${ars(r.total)}", style = MaterialTheme.typography.bodyMedium)
                    }
                }
                if (cancelable) {
                    TextButton(onClick = { confirmarCancelacion = true }) {
                        Text("Cancelar reserva (reembolso total hasta las ${hora(r.cancelableHasta!!)})")
                    }
                } else if (r.cancelableHasta != null) {
                    Text("Ya no se puede cancelar: el plazo con reembolso venció a las ${hora(r.cancelableHasta)}.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }

    if (confirmarCancelacion && r != null) {
        AlertDialog(
            onDismissRequest = { if (!cancelando) confirmarCancelacion = false },
            title = { Text("¿Cancelar la reserva?") },
            text = { Text("Te devolvemos ${ars(r.total)} a tu cuenta de Mercado Pago.") },
            confirmButton = {
                TextButton(enabled = !cancelando, onClick = {
                    cancelando = true
                    alcance.launch {
                        try {
                            val cancelada = app.api.cancelar(r.id)
                            app.sesion.borrarQr(r.id) // el QR de una reserva cancelada ya no sirve
                            alVolver(
                                if (cancelada.reembolso == "REEMBOLSO_FALLIDO") "Reserva cancelada. El reembolso de ${ars(r.total)} se está procesando."
                                else "Reserva cancelada. Te devolvimos ${ars(r.total)} a tu cuenta de Mercado Pago."
                            )
                        } catch (e: Exception) {
                            error = e.comoErrorDrivly().message
                            confirmarCancelacion = false
                        } finally {
                            cancelando = false
                        }
                    }
                }) { Text(if (cancelando) "Cancelando…" else "Sí, cancelar") }
            },
            dismissButton = {
                TextButton(enabled = !cancelando, onClick = { confirmarCancelacion = false }) { Text("No, volver") }
            },
        )
    }
}

private fun generarQr(contenido: String, lado: Int): Bitmap {
    val matriz = QRCodeWriter().encode(
        contenido, BarcodeFormat.QR_CODE, lado, lado,
        mapOf(EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M, EncodeHintType.MARGIN to 1),
    )
    val pixeles = IntArray(lado * lado) { i -> if (matriz[i % lado, i / lado]) 0xFF121824.toInt() else Color.WHITE }
    return Bitmap.createBitmap(pixeles, lado, lado, Bitmap.Config.ARGB_8888)
}
