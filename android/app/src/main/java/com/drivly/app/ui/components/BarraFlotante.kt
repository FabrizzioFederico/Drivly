package com.drivly.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

data class ItemBarra(val ruta: String, val titulo: String, val icono: ImageVector, val iconoElegido: ImageVector)

/** Alto de la barra (72 dp) + margen inferior (12 dp) + aire para que el último elemento no quede pegado. */
val ALTO_BARRA_FLOTANTE = 96.dp

/**
 * Espacio que cada pantalla deja abajo para que la barra flotante no tape su contenido
 * (0 en las pantallas sin barra: reservar, pago, ticket).
 */
val LocalEspacioBarra = compositionLocalOf { 0.dp }

/**
 * Muestra u oculta la barra según la dirección del scroll de cualquier lista de la pantalla, como Uber:
 * bajando se esconde para dar más lugar, subiendo vuelve. Se conecta con Modifier.nestedScroll en el
 * contenedor de la navegación, así ninguna pantalla tiene que avisar nada.
 */
class ScrollDeBarra : NestedScrollConnection {
    var visible by mutableStateOf(true)

    override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
        when {
            available.y < -UMBRAL -> visible = false // el dedo sube: el contenido baja
            available.y > UMBRAL -> visible = true
        }
        return Offset.Zero // sólo observa: no consume el scroll
    }

    private companion object {
        const val UMBRAL = 6f // ignora micro movimientos para que no titile
    }
}

/** Barra de navegación flotante (píldora con sombra, separada de los bordes) que entra y sale deslizando. */
@Composable
fun BarraFlotante(
    items: List<ItemBarra>,
    rutaActual: String?,
    visible: Boolean,
    alElegir: (String) -> Unit,
    modifier: Modifier = Modifier,
    margen: Dp = 12.dp,
) {
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = slideInVertically { it * 2 } + fadeIn(),
        exit = slideOutVertically { it * 2 } + fadeOut(),
    ) {
        Surface(
            modifier = Modifier
                .windowInsetsPadding(WindowInsets.navigationBars)
                .padding(horizontal = 24.dp, vertical = margen)
                .fillMaxWidth(),
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surface,
            shadowElevation = 10.dp,
            tonalElevation = 2.dp,
        ) {
            NavigationBar(
                containerColor = Color.Transparent,
                tonalElevation = 0.dp,
                windowInsets = WindowInsets(0, 0, 0, 0), // los insets ya los maneja el Surface
            ) {
                items.forEach { item ->
                    val elegido = item.ruta == rutaActual
                    NavigationBarItem(
                        selected = elegido,
                        onClick = { alElegir(item.ruta) },
                        icon = { Icon(if (elegido) item.iconoElegido else item.icono, contentDescription = null) },
                        label = { Text(item.titulo) },
                    )
                }
            }
        }
    }
}
