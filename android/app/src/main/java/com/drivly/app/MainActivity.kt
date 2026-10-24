package com.drivly.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocalParking
import androidx.compose.material.icons.outlined.QrCode2
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.drivly.app.ui.components.EstadoChip
import com.drivly.app.ui.theme.DrivlyTheme
import com.drivly.app.ui.theme.JetBrainsMono

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DrivlyTheme {
                MuestraDelTema()
            }
        }
    }
}

/** Pantalla temporal para ver el tema Material 3 de Drivly. La reemplaza el login. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MuestraDelTema() {
    var patente by remember { mutableStateOf("AB123CD") }
    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("Drivly") },
                navigationIcon = {
                    Icon(Icons.Filled.LocalParking, contentDescription = null, Modifier.padding(start = 16.dp),
                        tint = MaterialTheme.colorScheme.primary)
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Encontrá dónde estacionar", style = MaterialTheme.typography.headlineMedium)
            Text("Reservá tu lugar y pagá con Mercado Pago.", style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant)

            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically) {
                        Text("Cochera Thames", style = MaterialTheme.typography.titleMedium)
                        EstadoChip("HOLD", sufijo = "04:59")
                    }
                    Text("Malabia 2200, Palermo", style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("$ 4.080", style = MaterialTheme.typography.headlineSmall)
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EstadoChip("CONFIRMADA")
                EstadoChip("EN_CURSO")
                EstadoChip("CON_DEUDA")
            }

            OutlinedTextField(
                value = patente,
                onValueChange = { patente = it.uppercase() },
                label = { Text("Patente") },
                textStyle = MaterialTheme.typography.titleMedium.copy(fontFamily = JetBrainsMono, fontWeight = FontWeight.Bold),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(onClick = {}, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Text("Retener lugar por 5 min")
            }
            Button(
                onClick = {},
                modifier = Modifier.fillMaxWidth().height(56.dp),
                colors = ButtonDefaults.buttonColors(containerColor = DrivlyTheme.colores.accion,
                    contentColor = MaterialTheme.colorScheme.onSecondary),
            ) {
                Text("Pagar $ 4.080 con Mercado Pago")
            }
            OutlinedButton(onClick = {}, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Icon(Icons.Outlined.QrCode2, contentDescription = null, Modifier.size(20.dp))
                Spacer(Modifier.size(8.dp))
                Text("Ver mi ticket")
            }
        }
    }
}

@Preview(name = "Claro", showBackground = true)
@Composable
private fun MuestraClaraPreview() {
    DrivlyTheme(darkTheme = false) { MuestraDelTema() }
}

@Preview(name = "Oscuro", showBackground = true)
@Composable
private fun MuestraOscuraPreview() {
    DrivlyTheme(darkTheme = true) { MuestraDelTema() }
}
