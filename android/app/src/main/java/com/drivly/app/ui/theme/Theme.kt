package com.drivly.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val LightColorScheme = lightColorScheme(
    primary = Brand,
    onPrimary = Color.White,
    primaryContainer = BrandSoft,
    onPrimaryContainer = BrandInk,
    secondary = Action,
    onSecondary = Ink,
    // secondaryContainer pinta las selecciones (pestaña activa, duración elegida, chips): azul de marca
    secondaryContainer = BrandSoft,
    onSecondaryContainer = BrandInk,
    tertiary = Hold,
    onTertiary = Ink,
    tertiaryContainer = HoldSoft,
    onTertiaryContainer = HoldInk,
    error = DebtInk,
    onError = Color.White,
    errorContainer = DebtSoft,
    onErrorContainer = DebtInk,
    background = Paper,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    surfaceVariant = InkSoft,
    onSurfaceVariant = InkMuted,
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Paper,
    surfaceContainer = InkSoft,
    surfaceContainerHigh = InkSoft,
    surfaceContainerHighest = Color(0xFFE4E7EC), // sin esto Material 3 usa su lila por defecto
    surfaceBright = Color.White,
    surfaceDim = InkLine,
    outline = InkLine,
    outlineVariant = InkSoft,
    inverseSurface = Ink,
    inverseOnSurface = InkSoft,
    inversePrimary = BrandLight,
)

private val DarkColorScheme = darkColorScheme(
    primary = BrandLight,
    onPrimary = Color(0xFF002E73),
    primaryContainer = BrandDeep,
    onPrimaryContainer = BrandSoft,
    secondary = Action,
    onSecondary = Color(0xFF003828),
    secondaryContainer = Color(0xFF1B3A66),
    onSecondaryContainer = BrandSoft,
    tertiary = Hold,
    onTertiary = Color(0xFF3D1C00),
    tertiaryContainer = Color(0xFF6B3300),
    onTertiaryContainer = HoldSoft,
    error = DebtLight,
    onError = Color(0xFF3B0000),
    errorContainer = Color(0xFF7A1616),
    onErrorContainer = DebtSoft,
    // Negro puro de fondo y grises neutros para las superficies (como X / Instagram, sin tinte azul).
    // Las sombras no se ven sobre negro: las tarjetas se separan con un borde fino (ver Tarjeta).
    background = Negro,
    onBackground = BlancoTexto,
    surface = Negro,
    onSurface = BlancoTexto,
    surfaceVariant = Negro700,
    onSurfaceVariant = GrisTextoSecundario,
    surfaceContainerLowest = Negro,
    surfaceContainerLow = Negro900,
    surfaceContainer = Negro800,
    surfaceContainerHigh = Negro700,
    surfaceContainerHighest = Negro600,
    surfaceBright = Negro600,
    surfaceDim = Negro,
    outline = GrisContorno,
    outlineVariant = GrisBorde,
    inverseSurface = BlancoTexto,
    inverseOnSurface = Negro,
    inversePrimary = Brand,
)

// Bordes como en la web: tarjetas 12 dp (rounded-card), hojas 16 dp (rounded-sheet).
val DrivlyShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

/** Colores de estado de reserva que Material 3 no trae (HOLD, CONFIRMADA, CON_DEUDA...). */
@Immutable
data class EstadoColores(val fondo: Color, val texto: Color, val acento: Color)

@Immutable
data class DrivlyColores(
    val exito: EstadoColores,
    val retenida: EstadoColores,
    val deuda: EstadoColores,
    val accion: Color,
    /** En oscuro las elevaciones se reemplazan por bordes finos: las sombras no se ven sobre negro. */
    val oscuro: Boolean,
)

private val ColoresClaros = DrivlyColores(
    exito = EstadoColores(SuccessSoft, SuccessInk, Success),
    retenida = EstadoColores(HoldSoft, HoldInk, Hold),
    deuda = EstadoColores(DebtSoft, DebtInk, Debt),
    accion = Action,
    oscuro = false,
)

private val ColoresOscuros = DrivlyColores(
    exito = EstadoColores(Color(0xFF0B3B26), SuccessSoft, Success),
    retenida = EstadoColores(Color(0xFF4A2A0A), HoldSoft, Hold),
    deuda = EstadoColores(Color(0xFF4A1414), DebtSoft, DebtLight),
    accion = Action,
    oscuro = true,
)

val LocalDrivlyColores = staticCompositionLocalOf { ColoresClaros }

/**
 * Tema Material 3 de Drivly. Sin color dinámico (Material You) a propósito: la app mantiene los colores
 * de la marca en cualquier teléfono, igual que la web.
 */
@Composable
fun DrivlyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    CompositionLocalProvider(LocalDrivlyColores provides if (darkTheme) ColoresOscuros else ColoresClaros) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
            typography = Typography,
            shapes = DrivlyShapes,
            content = content,
        )
    }
}

/** Acceso corto: `DrivlyTheme.colores.retenida.fondo`. */
object DrivlyTheme {
    val colores: DrivlyColores
        @Composable get() = LocalDrivlyColores.current
}
