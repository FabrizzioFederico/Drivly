package com.drivly.app.ui.perfil

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.drivly.app.BuildConfig
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.api.Usuario
import com.drivly.app.ui.components.Tarjeta
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PerfilScreen() {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val alcance = rememberCoroutineScope()
    var usuario by remember { mutableStateOf<Usuario?>(null) }
    LaunchedEffect(Unit) { usuario = runCatching { app.api.yo() }.getOrNull() }

    Scaffold(topBar = { TopAppBar(title = { Text("Perfil") }) }) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Tarjeta(Modifier.fillMaxWidth()) {
                ListItem(
                    colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                    leadingContent = { Icon(Icons.Outlined.AccountCircle, contentDescription = null) },
                    headlineContent = { Text(usuario?.nombre?.ifBlank { null } ?: "Conductor") },
                    supportingContent = { Text(usuario?.email ?: "Cargando…") },
                )
                ListItem(
                    colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                    leadingContent = { Icon(Icons.Outlined.Info, contentDescription = null) },
                    headlineContent = { Text("Versión") },
                    supportingContent = { Text(BuildConfig.VERSION_NAME) },
                )
            }
            OutlinedButton(
                onClick = { alcance.launch { app.sesion.cerrar() } }, // la app vuelve sola al login
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Text("  Cerrar sesión", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}
