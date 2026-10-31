package com.drivly.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.drivly.app.data.api.GarajeDisponible
import com.drivly.app.ui.ars
import com.drivly.app.ui.theme.DrivlyTheme

/**
 * Garajes con lugar cerca de uno que no tiene (regla 6). `cercanos` null = todavía se están buscando.
 * El conductor elige uno y sigue reservando; el playero sólo se lo indica al cliente (sin `alElegir`).
 */
@Composable
fun ListaCercanos(titulo: String, cercanos: List<GarajeDisponible>?, alElegir: ((GarajeDisponible) -> Unit)? = null) {
    val secundario = MaterialTheme.colorScheme.onSurfaceVariant
    Column(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerLow, MaterialTheme.shapes.large).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(titulo, fontWeight = FontWeight.ExtraBold)
        when {
            cercanos == null -> Text("Buscando garajes con lugar…", color = secundario)
            cercanos.isEmpty() -> Text("No hay garajes Drivly con lugar en 1 km. Probá con otro horario.", color = secundario)
            else -> cercanos.forEach { FilaCercano(it, alElegir) }
        }
    }
}

@Composable
private fun FilaCercano(g: GarajeDisponible, alElegir: ((GarajeDisponible) -> Unit)?) {
    val secundario = MaterialTheme.colorScheme.onSurfaceVariant
    Row(
        Modifier.fillMaxWidth().then(if (alElegir != null) Modifier.clickable { alElegir(g) } else Modifier).padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(g.nombre, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${g.direccion} · a ${g.distanciaM} m", style = MaterialTheme.typography.bodySmall, color = secundario)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text("${g.lugaresLibres} libres", color = DrivlyTheme.colores.exito.texto, fontWeight = FontWeight.ExtraBold)
            Text("desde ${ars(g.precioDesde)} ${g.precioUnidad}", style = MaterialTheme.typography.bodySmall, color = secundario)
        }
    }
}
