package com.drivly.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.drivly.app.data.api.Resena
import com.drivly.app.ui.fecha

/** Amarillo de las estrellas: se lee igual sobre fondo claro y oscuro. */
val COLOR_ESTRELLA = Color(0xFFF5B400)

/** "★ 4,3 (12)". Sin reseñas no muestra nada: un garaje nuevo no aparece como "malo". */
@Composable
fun Calificacion(estrellas: Double?, cantidad: Int, modifier: Modifier = Modifier) {
    if (estrellas == null || cantidad == 0) return
    val promedio = "%.1f".format(estrellas).replace('.', ',')
    Row(
        modifier.semantics(mergeDescendants = true) {
            contentDescription = "$promedio de 5 estrellas, ${if (cantidad == 1) "1 opinión" else "$cantidad opiniones"}"
        },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(Icons.Filled.Star, contentDescription = null, tint = COLOR_ESTRELLA, modifier = Modifier.size(16.dp))
        Text(promedio, style = MaterialTheme.typography.labelLarge)
        Text("($cantidad)", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Estrellas fijas (las de una reseña). */
@Composable
fun Estrellas(valor: Int, tamano: Dp = 16.dp) {
    Row(Modifier.semantics(mergeDescendants = true) { contentDescription = "$valor de 5 estrellas" }) {
        for (i in 1..5) {
            Icon(if (i <= valor) Icons.Filled.Star else Icons.Outlined.StarOutline, contentDescription = null,
                tint = if (i <= valor) COLOR_ESTRELLA else MaterialTheme.colorScheme.outline, modifier = Modifier.size(tamano))
        }
    }
}

/** Cinco estrellas para tocar: cada una es un botón de 48 dp (se puede usar con TalkBack). */
@Composable
fun SelectorEstrellas(valor: Int, alCambiar: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
        for (i in 1..5) {
            Box(
                Modifier.size(48.dp).selectable(selected = i == valor, role = Role.RadioButton, onClick = { alCambiar(i) })
                    .semantics { contentDescription = if (i == 1) "1 estrella" else "$i estrellas" },
                contentAlignment = Alignment.Center,
            ) {
                Icon(if (i <= valor) Icons.Filled.Star else Icons.Outlined.StarOutline, contentDescription = null,
                    tint = if (i <= valor) COLOR_ESTRELLA else MaterialTheme.colorScheme.outline, modifier = Modifier.size(36.dp))
            }
        }
    }
}

private val TEXTO_ESTRELLAS = mapOf(1 to "Muy malo", 2 to "Malo", 3 to "Regular", 4 to "Bueno", 5 to "Excelente")

/** Calificar (o corregir) la estadía en un garaje. */
@Composable
fun DialogoCalificar(
    garaje: String,
    inicial: Int?,
    enviando: Boolean,
    error: String?,
    alEnviar: (Int, String) -> Unit,
    alCerrar: () -> Unit,
) {
    var estrellas by remember { mutableIntStateOf(inicial ?: 0) }
    var comentario by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("¿Cómo te fue en $garaje?") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SelectorEstrellas(estrellas) { estrellas = it }
                Text(TEXTO_ESTRELLAS[estrellas] ?: "Tocá las estrellas", style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.align(Alignment.CenterHorizontally))
                OutlinedTextField(
                    value = comentario,
                    onValueChange = { if (it.length <= 500) comentario = it },
                    label = { Text("Comentario (opcional)") },
                    supportingText = { Text("Lo ven los demás conductores y el garaje. ${comentario.length}/500") },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            TextButton(onClick = { alEnviar(estrellas, comentario) }, enabled = estrellas > 0 && !enviando) {
                Text(if (enviando) "Enviando…" else "Enviar")
            }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Ahora no") } },
    )
}

/** Opiniones de un garaje: las más nuevas primero, con la respuesta del garaje si la hay. */
@Composable
fun DialogoResenas(garaje: String, resenas: List<Resena>?, error: String?, alCerrar: () -> Unit) {
    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("Opiniones de $garaje") },
        text = {
            when {
                error != null -> Text(error, color = MaterialTheme.colorScheme.error)
                resenas == null -> Box(Modifier.fillMaxWidth().padding(24.dp), Alignment.Center) { CircularProgressIndicator() }
                resenas.isEmpty() -> Text("Todavía nadie calificó este garaje.")
                else -> LazyColumn(Modifier.heightIn(max = 420.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(resenas, key = { it.id }) { r ->
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Estrellas(r.estrellas)
                                Text("${r.autor} · ${fecha(r.creadaEn)}",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (r.comentario.isNotBlank()) Text(r.comentario, style = MaterialTheme.typography.bodyMedium)
                            if (r.respuesta.isNotBlank()) {
                                Text("Respuesta del garaje: ${r.respuesta}", style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(start = 12.dp))
                            }
                            HorizontalDivider(Modifier.padding(top = 8.dp))
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = alCerrar) { Text("Cerrar") } },
    )
}
