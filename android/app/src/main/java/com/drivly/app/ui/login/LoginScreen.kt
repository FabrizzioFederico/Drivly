package com.drivly.app.ui.login

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocalParking
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.credentials.CredentialManager
import androidx.credentials.CredentialOption
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.BuildConfig
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.Sesion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoDevLogin
import com.drivly.app.data.api.PedidoEmail
import com.drivly.app.data.api.PedidoGoogleLogin
import com.drivly.app.data.api.PedidoLogin
import com.drivly.app.data.api.PedidoRegistro
import com.drivly.app.data.api.RespuestaLogin
import com.drivly.app.data.comoErrorDrivly
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import kotlinx.coroutines.launch

private val ROLES_DE_LA_APP = setOf("CONDUCTOR", "PLAYERO")

class LoginViewModel(private val api: DrivlyApi, private val sesion: Sesion) : ViewModel() {
    var cargando by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    /** Mensaje informativo (no es un error): "te mandamos un email...". */
    var aviso by mutableStateOf<String?>(null)
        private set

    /** Email de una cuenta creada o sin activar: el formulario vuelve a "Ingresar" y ofrece reenviar el link. */
    var pendienteDeActivar by mutableStateOf<String?>(null)
        private set

    /** El último email con el que se intentó ingresar: para reenviar el link si la cuenta no está activada. */
    private var ultimoEmail: String? = null

    fun conGoogle(idToken: String) = ingresar { api.googleLogin(PedidoGoogleLogin(idToken)) }

    /** Cuenta común con email y contraseña. */
    fun conEmail(email: String, password: String) {
        ultimoEmail = email.trim()
        if (pendienteDeActivar != null && pendienteDeActivar != ultimoEmail) pendienteDeActivar = null
        ingresar { api.login(PedidoLogin(email.trim(), password)) }
    }

    /**
     * La cuenta nueva siempre es de conductor (el administrador la pasa a playero desde el portal web) y queda
     * sin activar hasta tocar el link del email.
     */
    fun registrarse(nombre: String, email: String, password: String) = tarea {
        val r = api.registro(PedidoRegistro(nombre.trim(), email.trim(), password))
        pendienteDeActivar = r.email
        if (r.emailEnviado) aviso = r.detail else error = r.detail
    }

    fun reenviarActivacion() = tarea {
        val email = pendienteDeActivar ?: return@tarea
        api.reenviarActivacion(PedidoEmail(email))
        aviso = "Te mandamos un email nuevo a $email. Revisá también la carpeta de spam."
    }

    /** Acceso rápido de desarrollo (POST /auth/dev-login/, sólo con DEBUG=True en el backend). */
    fun desarrollo(rol: String = "CONDUCTOR") = ingresar { api.devLogin(PedidoDevLogin(rol)) }

    fun mostrarError(mensaje: String) {
        error = mensaje
    }

    fun limpiarError() {
        error = null
        aviso = null
    }

    private fun ingresar(pedido: suspend () -> RespuestaLogin) = tarea {
        val r = pedido()
        if (r.user.rol !in ROLES_DE_LA_APP) {
            error = "Esta app es para conductores y playeros. Los garajes se administran desde el portal web."
        } else {
            sesion.guardar(r.access, r.refresh, r.user.nombre, r.user.rol) // la navegación reacciona al guardar
        }
    }

    private fun tarea(bloque: suspend () -> Unit) {
        cargando = true
        error = null
        aviso = null
        viewModelScope.launch {
            try {
                bloque()
            } catch (e: Exception) {
                val causa = e.comoErrorDrivly()
                error = causa.message
                if (causa.codigo == "CUENTA_SIN_ACTIVAR") pendienteDeActivar = pendienteDeActivar ?: ultimoEmail
            } finally {
                cargando = false
            }
        }
    }
}

@Composable
fun LoginScreen() {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val vm: LoginViewModel = viewModel { LoginViewModel(app.api, app.sesion) }
    val context = LocalContext.current
    val alcance = rememberCoroutineScope()

    Scaffold { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(24.dp))
            Icon(Icons.Filled.LocalParking, contentDescription = null, Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(16.dp))
            Text("Drivly", style = MaterialTheme.typography.displaySmall)
            Text("Reservá tu lugar y pagá con Mercado Pago.", style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            Spacer(Modifier.height(32.dp))

            if (BuildConfig.GOOGLE_WEB_CLIENT_ID.isNotBlank()) {
                Button(
                    onClick = {
                        alcance.launch {
                            try {
                                pedirTokenDeGoogle(context)?.let(vm::conGoogle)
                            } catch (e: GetCredentialException) {
                                // En debug se muestra el detalle: [28444] = falta el client ID Android (paquete + SHA-1)
                                val detalle = if (BuildConfig.DEBUG) "\n(${e.type}: ${e.message})" else ""
                                vm.mostrarError("No se pudo iniciar sesión con Google. Intentá nuevamente.$detalle")
                            } catch (e: GoogleIdTokenParsingException) {
                                vm.mostrarError("Google devolvió una respuesta inválida. Intentá nuevamente.")
                            }
                        }
                    },
                    enabled = !vm.cargando,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                ) { Text("Ingresar con Google") }
                Separador("o con tu email")
            }

            FormularioEmail(vm)

            if (BuildConfig.DEBUG) {
                Separador("desarrollo")
                OutlinedButton(onClick = { vm.desarrollo() }, enabled = !vm.cargando,
                    modifier = Modifier.fillMaxWidth().height(56.dp)) {
                    Text("Acceso rápido de desarrollo")
                }
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = { vm.desarrollo("PLAYERO") }, enabled = !vm.cargando,
                    modifier = Modifier.fillMaxWidth().height(56.dp)) {
                    Text("Acceso rápido como playero")
                }
            }

            Spacer(Modifier.height(24.dp))
            if (vm.cargando) CircularProgressIndicator()
            vm.aviso?.let {
                Text(it, color = MaterialTheme.colorScheme.onSurface, textAlign = TextAlign.Center,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
            vm.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
            if (vm.pendienteDeActivar != null && !vm.cargando) {
                TextButton(onClick = vm::reenviarActivacion) { Text("Reenviar email de activación") }
            }
        }
    }
}

@Composable
private fun Separador(texto: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 20.dp), verticalAlignment = Alignment.CenterVertically) {
        HorizontalDivider(Modifier.weight(1f))
        Text(texto, Modifier.padding(horizontal = 12.dp), style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        HorizontalDivider(Modifier.weight(1f))
    }
}

/** Ingresar o crear una cuenta común. La cuenta nueva es de conductor. */
@Composable
private fun FormularioEmail(vm: LoginViewModel) {
    var creando by rememberSaveable { mutableStateOf(false) }
    var nombre by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var verPassword by rememberSaveable { mutableStateOf(false) }
    val foco = LocalFocusManager.current

    // Cuenta creada: vuelve a "Ingresar" con el email cargado, para entrar después de tocar el link del email
    LaunchedEffect(vm.pendienteDeActivar) {
        val pendiente = vm.pendienteDeActivar ?: return@LaunchedEffect
        if (creando) {
            creando = false
            email = pendiente
            password = ""
        }
    }

    val completo = email.contains("@") && password.isNotEmpty() &&
        (!creando || (nombre.isNotBlank() && password.length >= 8))
    val enviar = {
        foco.clearFocus()
        if (creando) vm.registrarse(nombre, email, password) else vm.conEmail(email, password)
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf("Ingresar", "Crear cuenta").forEachIndexed { i, etiqueta ->
                SegmentedButton(
                    selected = creando == (i == 1),
                    onClick = { creando = i == 1; vm.limpiarError() },
                    shape = SegmentedButtonDefaults.itemShape(i, 2),
                ) { Text(etiqueta) }
            }
        }
        if (creando) {
            OutlinedTextField(
                value = nombre, onValueChange = { nombre = it.take(150) },
                label = { Text("Nombre y apellido") }, singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
        }
        OutlinedTextField(
            value = email, onValueChange = { email = it.trim() },
            label = { Text("Email") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = password, onValueChange = { password = it },
            label = { Text("Contraseña") }, singleLine = true,
            supportingText = if (creando) ({ Text("Al menos 8 caracteres, que no sean sólo números.") }) else null,
            visualTransformation = if (verPassword) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                IconButton(onClick = { verPassword = !verPassword }) {
                    Icon(if (verPassword) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                        contentDescription = if (verPassword) "Ocultar contraseña" else "Mostrar contraseña")
                }
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { if (completo && !vm.cargando) enviar() }),
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            onClick = enviar,
            enabled = completo && !vm.cargando,
            modifier = Modifier.fillMaxWidth().height(56.dp),
        ) { Text(if (creando) "Crear cuenta" else "Ingresar") }
        if (creando) {
            Text(
                "Las cuentas nuevas son de conductor. Si trabajás en un garaje, pedile al administrador " +
                    "que te agregue como playero con este email.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * Credential Manager: devuelve el ID token de Google, o null si el usuario canceló.
 * Primero ofrece las cuentas del teléfono; si no hay ninguna (NoCredentialException),
 * abre el flujo "Sign in with Google", que permite agregar una cuenta.
 */
private suspend fun pedirTokenDeGoogle(context: Context): String? {
    val selector = GetGoogleIdOption.Builder()
        .setServerClientId(BuildConfig.GOOGLE_WEB_CLIENT_ID) // el backend valida que el token sea para este client ID
        .setFilterByAuthorizedAccounts(false)
        .build()
    return try {
        try {
            obtenerToken(context, selector)
        } catch (e: NoCredentialException) {
            obtenerToken(context, GetSignInWithGoogleOption.Builder(BuildConfig.GOOGLE_WEB_CLIENT_ID).build())
        }
    } catch (e: GetCredentialCancellationException) {
        null // el usuario cerró el selector de cuentas
    }
}

private suspend fun obtenerToken(context: Context, opcion: CredentialOption): String {
    val respuesta = CredentialManager.create(context)
        .getCredential(context, GetCredentialRequest.Builder().addCredentialOption(opcion).build())
    return GoogleIdTokenCredential.createFrom(respuesta.credential.data).idToken
}
