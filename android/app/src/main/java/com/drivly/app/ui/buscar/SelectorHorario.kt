package com.drivly.app.ui.buscar

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

private val DIA = DateTimeFormatter.ofPattern("EEE d MMM", Locale.forLanguageTag("es-AR"))
private val HORA = DateTimeFormatter.ofPattern("HH:mm")
private val DURACIONES = listOf(1, 2, 3, 6)

/**
 * Cuándo y cuánto tiempo: fecha (DatePicker), hora de llegada (TimePicker) y duración (botones segmentados).
 * Nunca deja elegir un inicio en el pasado: el backend lo rechazaría.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SelectorHorario(horario: Horario, alCambiar: (Horario) -> Unit, modifier: Modifier = Modifier) {
    var dialogo by remember { mutableStateOf<String?>(null) } // "fecha" | "hora"
    val local = horario.inicio.atZoneSameInstant(ZoneId.systemDefault())
    val hoy = LocalDate.now()

    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AssistChip(
                onClick = { dialogo = "fecha" },
                label = { Text(if (local.toLocalDate() == hoy) "Hoy" else local.format(DIA)) },
                leadingIcon = { Icon(Icons.Outlined.CalendarMonth, null, Modifier.size(AssistChipDefaults.IconSize)) },
            )
            AssistChip(
                onClick = { dialogo = "hora" },
                label = { Text("Llego ${local.format(HORA)} · salgo ${horario.fin.atZoneSameInstant(ZoneId.systemDefault()).format(HORA)}") },
                leadingIcon = { Icon(Icons.Outlined.Schedule, null, Modifier.size(AssistChipDefaults.IconSize)) },
            )
        }
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            DURACIONES.forEachIndexed { i, h ->
                SegmentedButton(
                    selected = horario.horas == h,
                    onClick = { alCambiar(horario.copy(horas = h)) },
                    shape = SegmentedButtonDefaults.itemShape(i, DURACIONES.size),
                ) { Text("$h h") }
            }
        }
    }

    when (dialogo) {
        "fecha" -> {
            val estado = rememberDatePickerState(
                initialSelectedDateMillis = local.toLocalDate().atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
                selectableDates = object : SelectableDates {
                    // DatePicker trabaja en UTC: se compara la fecha calendario, no el instante
                    override fun isSelectableDate(utcTimeMillis: Long) =
                        !Instant.ofEpochMilli(utcTimeMillis).atZone(ZoneOffset.UTC).toLocalDate().isBefore(hoy)
                },
            )
            DatePickerDialog(
                onDismissRequest = { dialogo = null },
                confirmButton = {
                    TextButton(onClick = {
                        estado.selectedDateMillis?.let { ms ->
                            val fecha = Instant.ofEpochMilli(ms).atZone(ZoneOffset.UTC).toLocalDate()
                            alCambiar(conInicio(horario, fecha, local.toLocalTime()))
                        }
                        dialogo = null
                    }) { Text("Aceptar") }
                },
                dismissButton = { TextButton(onClick = { dialogo = null }) { Text("Cancelar") } },
            ) { DatePicker(estado) }
        }
        "hora" -> {
            val estado = rememberTimePickerState(local.hour, local.minute, is24Hour = true)
            AlertDialog(
                onDismissRequest = { dialogo = null },
                title = { Text("¿A qué hora llegás?", style = MaterialTheme.typography.titleMedium) },
                text = { TimePicker(estado, Modifier.padding(top = 8.dp)) },
                confirmButton = {
                    TextButton(onClick = {
                        alCambiar(conInicio(horario, local.toLocalDate(), LocalTime.of(estado.hour, estado.minute)))
                        dialogo = null
                    }) { Text("Aceptar") }
                },
                dismissButton = { TextButton(onClick = { dialogo = null }) { Text("Cancelar") } },
            )
        }
    }
}

/** Arma el nuevo inicio; si quedó en el pasado vuelve a "ahora" (redondeado al cuarto de hora). */
private fun conInicio(horario: Horario, fecha: LocalDate, hora: LocalTime): Horario {
    val inicio = fecha.atTime(hora).atZone(ZoneId.systemDefault()).toOffsetDateTime().truncatedTo(ChronoUnit.MINUTES)
    return if (inicio.isBefore(OffsetDateTime.now().minusMinutes(1))) Horario.desdeAhora(horario.horas)
    else horario.copy(inicio = inicio)
}
