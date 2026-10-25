package com.drivly.app.ui.perfil

import android.graphics.Bitmap
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.BuildConfig
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.Sesion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoCambioEmail
import com.drivly.app.data.api.PedidoCodigo
import com.drivly.app.data.api.PedidoPerfil
import com.drivly.app.data.api.Usuario
import com.drivly.app.data.comoErrorDrivly
import com.drivly.app.data.descargarImagen
import com.drivly.app.data.fotoParaSubir
import com.drivly.app.data.urlDeMedia
import com.drivly.app.ui.components.LocalEspacioBarra
import com.drivly.app.ui.components.Tarjeta
import kotlinx.coroutines.launch
import okhttp3.MultipartBody

/** Valores del backend (cuentas.models.Genero) y cómo se muestran. "" = sin especificar. */
private val GENEROS = listOf(
    "" to "Sin especificar",
    "FEMENINO" to "Femenino",
    "MASCULINO" to "Masculino",
    "NO_BINARIO" to "No binario",
    "PREFIERO_NO_DECIR" to "Prefiero no decirlo",
)

class PerfilViewModel(private val api: DrivlyApi, private val sesion: Sesion) : ViewModel() {
    var usuario by mutableStateOf<Usuario?>(null)
        private set
    var nombre by mutableStateOf("")
    var genero by mutableStateOf("")
    var telefono by mutableStateOf("")
    var ocupado by mutableStateOf(false)
        private set
    var subiendoFoto by mutableStateOf(false)
        private set
    /** Mensaje para el snackbar (éxito o error). */
    var aviso by mutableStateOf<String?>(null)

    val hayCambios: Boolean
        get() = usuario?.let { it.nombre != nombre.trim() || it.genero != genero || it.telefono != telefono.trim() } == true

    init {
        viewModelScope.launch {
            runCatching { api.yo() }.onSuccess(::cargarFormulario).onFailure { aviso = it.comoErrorDrivly().message }
        }
    }

    private fun cargarFormulario(u: Usuario) {
        usuario = u
        nombre = u.nombre
        genero = u.genero
        telefono = u.telefono
    }

    fun guardar() = tarea("Datos guardados.") {
        val u = api.actualizarPerfil(PedidoPerfil(nombre.trim(), genero, telefono.trim()))
        cargarFormulario(u)
        sesion.guardarNombre(u.nombre)
    }

    // Foto y email se guardan por su lado: sólo se actualiza `usuario`, sin pisar lo que se esté editando

    fun subirFoto(preparar: suspend () -> MultipartBody.Part) {
        subiendoFoto = true
        viewModelScope.launch {
            try {
                usuario = api.subirFoto(preparar())
                aviso = "Foto actualizada."
            } catch (e: Exception) {
                aviso = e.comoErrorDrivly().message
            } finally {
                subiendoFoto = false
            }
        }
    }

    fun quitarFoto() = tarea("Foto eliminada.") { usuario = api.borrarFoto() }

    /** Paso 1: el servidor manda un código al email nuevo. Devuelve el error o null. */
    suspend fun pedirCodigo(email: String): String? = try {
        aviso = api.pedirCambioEmail(PedidoCambioEmail(email.trim())).detail.ifBlank { null }
        null
    } catch (e: Exception) {
        e.comoErrorDrivly().message
    }

    /** Paso 2: con el código correcto se aplica el cambio. Devuelve el error o null. */
    suspend fun confirmarCodigo(codigo: String): String? = try {
        usuario = api.confirmarEmail(PedidoCodigo(codigo.trim()))
        aviso = "Email actualizado."
        null
    } catch (e: Exception) {
        e.comoErrorDrivly().message
    }

    fun cerrarSesion() = viewModelScope.launch { sesion.cerrar() }

    private fun tarea(exito: String, bloque: suspend () -> Unit) {
        ocupado = true
        viewModelScope.launch {
            try {
                bloque()
                aviso = exito
            } catch (e: Exception) {
                aviso = e.comoErrorDrivly().message
            } finally {
                ocupado = false
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PerfilScreen() {
    val context = LocalContext.current
    val app = context.applicationContext as DrivlyApplication
    val vm: PerfilViewModel = viewModel { PerfilViewModel(app.api, app.sesion) }
    val avisos = remember { SnackbarHostState() }
    var cambiandoEmail by remember { mutableStateOf(false) }

    // Photo Picker del sistema: no necesita permiso de almacenamiento
    val elegirFoto = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri: Uri? ->
        if (uri != null) vm.subirFoto { fotoParaSubir(context, uri) }
    }

    LaunchedEffect(vm.aviso) {
        vm.aviso?.let {
            vm.aviso = null
            avisos.showSnackbar(it)
        }
    }

    val u = vm.usuario
    Scaffold(
        snackbarHost = { SnackbarHost(avisos) },
        // El título es el nombre del usuario ("Perfil" mientras carga o si todavía no tiene uno)
        topBar = {
            TopAppBar(title = { Text(u?.nombre?.ifBlank { null } ?: "Perfil", maxLines = 1, overflow = TextOverflow.Ellipsis) })
        },
    ) { padding ->
        if (u == null) {
            Box(Modifier.fillMaxSize().padding(padding), Alignment.Center) { CircularProgressIndicator() }
            return@Scaffold
        }
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState())
                .padding(16.dp).padding(bottom = LocalEspacioBarra.current),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Avatar(
                usuario = u,
                cargando = vm.subiendoFoto,
                alCambiar = { elegirFoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                alQuitar = vm::quitarFoto,
            )

            Tarjeta(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = vm.nombre, onValueChange = { vm.nombre = it.take(150) },
                        label = { Text("Nombre") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = u.email, onValueChange = {}, readOnly = true,
                        label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                        trailingIcon = { TextButton(onClick = { cambiandoEmail = true }) { Text("Cambiar") } },
                    )
                    OutlinedTextField(
                        value = vm.telefono, onValueChange = { vm.telefono = it.take(20) },
                        label = { Text("Teléfono") }, placeholder = { Text("+54 9 11 1234-5678") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), modifier = Modifier.fillMaxWidth(),
                    )
                    SelectorGenero(vm.genero) { vm.genero = it }
                }
            }

            Button(
                onClick = vm::guardar,
                enabled = vm.hayCambios && !vm.ocupado,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text(if (vm.ocupado) "Guardando…" else "Guardar cambios") }

            OutlinedButton(onClick = { vm.cerrarSesion() }, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Text("  Cerrar sesión", style = MaterialTheme.typography.labelLarge)
            }
            Text("Drivly ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

    if (cambiandoEmail) DialogoCambioEmail(vm, alCerrar = { cambiandoEmail = false })
}

/** Foto circular (o iniciales); al tocarla se elige otra o se quita la actual. */
@Composable
private fun Avatar(usuario: Usuario, cargando: Boolean, alCambiar: () -> Unit, alQuitar: () -> Unit) {
    var menu by remember { mutableStateOf(false) }
    val url = urlDeMedia(usuario.foto)
    val imagen by produceState<Bitmap?>(null, url) { value = url?.let { descargarImagen(it) } }
    val iniciales = usuario.nombre.split(" ").filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }
        .ifBlank { usuario.email.first().uppercase() }

    Box {
        Box(
            Modifier.size(112.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer)
                .clickable(onClickLabel = "Cambiar foto de perfil") { if (usuario.foto != null) menu = true else alCambiar() },
            contentAlignment = Alignment.Center,
        ) {
            val bitmap = imagen
            if (bitmap != null) {
                Image(bitmap.asImageBitmap(), contentDescription = "Foto de perfil", contentScale = ContentScale.Crop,
                    modifier = Modifier.size(112.dp))
            } else {
                Text(iniciales, style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            if (cargando) CircularProgressIndicator()
        }
        Surface(
            shape = CircleShape, color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.align(Alignment.BottomEnd).size(36.dp),
        ) {
            Icon(Icons.Filled.PhotoCamera, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.padding(8.dp))
        }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
            DropdownMenuItem(text = { Text("Cambiar foto") }, onClick = { menu = false; alCambiar() })
            DropdownMenuItem(text = { Text("Quitar foto") }, onClick = { menu = false; alQuitar() })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SelectorGenero(actual: String, alElegir: (String) -> Unit) {
    var abierto by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = abierto, onExpandedChange = { abierto = it }) {
        OutlinedTextField(
            value = GENEROS.firstOrNull { it.first == actual }?.second ?: "Sin especificar",
            onValueChange = {}, readOnly = true, label = { Text("Género") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = abierto) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(expanded = abierto, onDismissRequest = { abierto = false }) {
            GENEROS.forEach { (valor, texto) ->
                DropdownMenuItem(text = { Text(texto) }, onClick = { abierto = false; alElegir(valor) })
            }
        }
    }
}

/** Cambio de email en dos pasos: email nuevo -> código de 6 dígitos que llega a ese email. */
@Composable
private fun DialogoCambioEmail(vm: PerfilViewModel, alCerrar: () -> Unit) {
    val alcance = rememberCoroutineScope()
    var email by remember { mutableStateOf("") }
    var codigo by remember { mutableStateOf("") }
    var esperandoCodigo by remember { mutableStateOf(false) }
    var enviando by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = { if (!enviando) alCerrar() },
        title = { Text(if (esperandoCodigo) "Revisá tu email" else "Cambiar email") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (!esperandoCodigo) {
                    Text("Te vamos a mandar un código para confirmar que el email es tuyo.")
                    OutlinedTextField(
                        value = email, onValueChange = { email = it; error = null }, label = { Text("Email nuevo") },
                        singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                        isError = error != null, modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    Text("Ingresá el código de 6 números que mandamos a ${email.trim()}. Vence en 15 minutos.")
                    OutlinedTextField(
                        value = codigo, onValueChange = { codigo = it.filter(Char::isDigit).take(6); error = null },
                        label = { Text("Código") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                        isError = error != null, modifier = Modifier.fillMaxWidth(),
                    )
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = {
            TextButton(
                enabled = !enviando && (if (esperandoCodigo) codigo.length == 6 else email.contains("@")),
                onClick = {
                    enviando = true
                    alcance.launch {
                        if (!esperandoCodigo) {
                            error = vm.pedirCodigo(email)
                            if (error == null) esperandoCodigo = true
                        } else {
                            error = vm.confirmarCodigo(codigo)
                            if (error == null) alCerrar()
                        }
                        enviando = false
                    }
                },
            ) { Text(if (enviando) "Enviando…" else if (esperandoCodigo) "Confirmar" else "Enviar código") }
        },
        dismissButton = { TextButton(enabled = !enviando, onClick = alCerrar) { Text("Cancelar") } },
    )
}
