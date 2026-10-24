package com.drivly.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.drivly.app.R

// Fuentes variables incluidas en res/font (mismas que la web): un archivo por familia, cada peso es una variación.
@OptIn(ExperimentalTextApi::class)
private fun variable(res: Int, vararg pesos: FontWeight) = FontFamily(
    pesos.map { Font(res, it, variationSettings = FontVariation.Settings(FontVariation.weight(it.weight))) }
)

val PlusJakartaSans = variable(
    R.font.plus_jakarta_sans,
    FontWeight.Normal, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold, FontWeight.ExtraBold,
)

/** Patentes, IDs de reserva y montos tabulares. */
val JetBrainsMono = variable(R.font.jetbrains_mono, FontWeight.Medium, FontWeight.Bold)

private val base = Typography()

private fun TextStyle.jakarta(peso: FontWeight) = copy(fontFamily = PlusJakartaSans, fontWeight = peso)

// Escala de Material 3 con la fuente de Drivly; títulos más pesados, como en la web (font-extrabold).
val Typography = Typography(
    displayLarge = base.displayLarge.jakarta(FontWeight.ExtraBold),
    displayMedium = base.displayMedium.jakarta(FontWeight.ExtraBold),
    displaySmall = base.displaySmall.jakarta(FontWeight.ExtraBold),
    headlineLarge = base.headlineLarge.jakarta(FontWeight.ExtraBold),
    headlineMedium = base.headlineMedium.jakarta(FontWeight.ExtraBold),
    headlineSmall = base.headlineSmall.jakarta(FontWeight.ExtraBold),
    titleLarge = base.titleLarge.jakarta(FontWeight.ExtraBold),
    titleMedium = base.titleMedium.jakarta(FontWeight.Bold),
    titleSmall = base.titleSmall.jakarta(FontWeight.Bold),
    bodyLarge = base.bodyLarge.jakarta(FontWeight.Normal),
    bodyMedium = base.bodyMedium.jakarta(FontWeight.Normal),
    bodySmall = base.bodySmall.jakarta(FontWeight.Normal),
    labelLarge = base.labelLarge.jakarta(FontWeight.Bold),
    labelMedium = base.labelMedium.jakarta(FontWeight.SemiBold),
    labelSmall = base.labelSmall.jakarta(FontWeight.SemiBold).copy(letterSpacing = 0.8.sp),
)
