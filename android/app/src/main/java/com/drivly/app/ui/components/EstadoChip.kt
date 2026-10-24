package com.drivly.app.ui.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.drivly.app.ui.theme.DrivlyTheme
import com.drivly.app.ui.theme.EstadoColores
import com.drivly.app.ui.theme.JetBrainsMono

private val ETIQUETAS = mapOf(
    "HOLD" to "HOLD", "CONFIRMADA" to "CONFIRMADA", "EN_CURSO" to "EN CURSO", "CON_DEUDA" to "CON DEUDA",
    "FINALIZADA" to "FINALIZADA", "EXPIRADA" to "EXPIRADA", "CANCELADA" to "CANCELADA",
    "NO_SHOW" to "NO SE PRESENTÓ", "SIN_LUGAR" to "SIN LUGAR",
)

/**
 * Estado de una reserva, igual que StatusBadge de la web. HOLD y CON_DEUDA llevan punto pulsante.
 * `sufijo` sirve para la cuenta regresiva del hold: EstadoChip("HOLD", sufijo = "04:59").
 */
@Composable
fun EstadoChip(estado: String, modifier: Modifier = Modifier, sufijo: String? = null) {
    val c = coloresDe(estado)
    Row(
        modifier = modifier
            .height(28.dp)
            .clip(CircleShape)
            .background(c.fondo)
            .padding(horizontal = 12.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Punto(c, pulsa = estado == "HOLD" || estado == "CON_DEUDA")
        Text(ETIQUETAS[estado] ?: estado, style = MaterialTheme.typography.labelSmall, color = c.texto)
        if (sufijo != null) {
            Text(sufijo, style = MaterialTheme.typography.labelSmall.copy(fontFamily = JetBrainsMono), color = c.texto)
        }
    }
}

@Composable
private fun coloresDe(estado: String): EstadoColores {
    val d = DrivlyTheme.colores
    val esquema = MaterialTheme.colorScheme
    return when (estado) {
        "HOLD" -> d.retenida
        "CONFIRMADA" -> d.exito
        "EN_CURSO" -> EstadoColores(esquema.primaryContainer, esquema.onPrimaryContainer, esquema.primary)
        "CON_DEUDA", "SIN_LUGAR" -> d.deuda
        else -> EstadoColores(esquema.surfaceVariant, esquema.onSurfaceVariant, esquema.outline)
    }
}

@Composable
private fun Punto(c: EstadoColores, pulsa: Boolean) {
    Box(Modifier.size(8.dp), contentAlignment = Alignment.Center) {
        if (pulsa) {
            val t = rememberInfiniteTransition(label = "pulso")
            val escala by t.animateFloat(1f, 2.2f, infiniteRepeatable(tween(1000), RepeatMode.Restart), label = "escala")
            val opacidad by t.animateFloat(0.75f, 0f, infiniteRepeatable(tween(1000), RepeatMode.Restart), label = "opacidad")
            Box(Modifier.size(8.dp).scale(escala).alpha(opacidad).clip(CircleShape).background(c.acento))
        }
        Box(Modifier.size(8.dp).clip(CircleShape).background(c.acento))
    }
}
