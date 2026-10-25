package com.drivly.app.ui

import java.math.BigDecimal
import java.text.NumberFormat
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

private val ARGENTINA = Locale.forLanguageTag("es-AR")
private val HORA = DateTimeFormatter.ofPattern("HH:mm")
private val FECHA_HORA = DateTimeFormatter.ofPattern("EEE d 'de' MMM, HH:mm", ARGENTINA)

/** "4080.00" -> "$ 4.080" (como ars() de la web). */
fun ars(monto: String): String {
    val formato = NumberFormat.getCurrencyInstance(ARGENTINA).apply { maximumFractionDigits = 0 }
    return formato.format(runCatching { BigDecimal(monto) }.getOrDefault(BigDecimal.ZERO))
}

fun instante(iso: String): OffsetDateTime = OffsetDateTime.parse(iso)

/** Para mandar a la API: siempre en UTC ("...Z"), así un "+03:00" nunca viaja en la URL (se leería como espacio). */
fun OffsetDateTime.iso(): String = withOffsetSameInstant(ZoneOffset.UTC).toString()

/** ISO del servidor (UTC) -> hora local del teléfono. */
fun hora(iso: String): String = instante(iso).atZoneSameInstant(ZoneId.systemDefault()).format(HORA)

fun fechaHora(iso: String): String = instante(iso).atZoneSameInstant(ZoneId.systemDefault()).format(FECHA_HORA)
