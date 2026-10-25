package com.drivly.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.drivly.app.ui.theme.DrivlyTheme

/**
 * Tarjeta de Drivly. Claro: superficie blanca con sombra suave (shadow-card de la web).
 * Oscuro: gris casi negro con borde fino, porque sobre fondo negro las sombras no se ven.
 */
@Composable
fun Tarjeta(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    enabled: Boolean = true,
    borde: BorderStroke? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val oscuro = DrivlyTheme.colores.oscuro
    val colores = CardDefaults.cardColors(
        containerColor = if (oscuro) MaterialTheme.colorScheme.surfaceContainerLow else MaterialTheme.colorScheme.surface,
    )
    val elevacion = CardDefaults.cardElevation(defaultElevation = if (oscuro) 0.dp else 2.dp)
    val bordeFinal = borde ?: bordeOscuro()
    if (onClick != null) {
        Card(onClick = onClick, modifier = modifier, enabled = enabled, colors = colores, elevation = elevacion,
            border = bordeFinal, content = content)
    } else {
        Card(modifier = modifier, colors = colores, elevation = elevacion, border = bordeFinal, content = content)
    }
}

/** Borde fino que reemplaza a la sombra en modo oscuro (null en claro). */
@Composable
fun bordeOscuro(): BorderStroke? =
    if (DrivlyTheme.colores.oscuro) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null
