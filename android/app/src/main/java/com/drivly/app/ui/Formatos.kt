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
private val FECHA = DateTimeFormatter.ofPattern("d 'de' MMM yyyy", ARGENTINA)

/** Por hora y presencial duran horas; el resto son abonos, que duran semanas o meses. */
fun esAbono(modalidad: String): Boolean = modalidad != "HORA" && modalidad != "PRESENCIAL"

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

fun fecha(iso: String): String = instante(iso).atZoneSameInstant(ZoneId.systemDefault()).format(FECHA)

/** "vie 30 de oct, 18:00 a 21:00", o "Abono del 30 de oct 2026 al 30 de nov 2026". */
fun periodo(modalidad: String, inicio: String, fin: String): String =
    if (esAbono(modalidad)) "Abono del ${fecha(inicio)} al ${fecha(fin)}" else "${fechaHora(inicio)} a ${hora(fin)}"
