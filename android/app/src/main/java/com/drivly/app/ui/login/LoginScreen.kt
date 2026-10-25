package com.drivly.app.ui.login

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocalParking
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.drivly.app.BuildConfig
import com.drivly.app.DrivlyApplication
import com.drivly.app.data.Sesion
import com.drivly.app.data.api.DrivlyApi
import com.drivly.app.data.api.PedidoGoogleLogin
import com.drivly.app.data.api.RespuestaLogin
import com.drivly.app.data.comoErrorDrivly
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import kotlinx.coroutines.launch

class LoginViewModel(private val api: DrivlyApi, private val sesion: Sesion) : ViewModel() {
    var cargando by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    fun conGoogle(idToken: String) = ingresar { api.googleLogin(PedidoGoogleLogin(idToken)) }

    /** Acceso rápido de desarrollo (POST /auth/dev-login/, sólo con DEBUG=True en el backend). */
    fun desarrollo() = ingresar { api.devLogin() }

    fun mostrarError(mensaje: String) {
        error = mensaje
    }

    private fun ingresar(pedido: suspend () -> RespuestaLogin) {
        cargando = true
        error = null
        viewModelScope.launch {
            try {
                val r = pedido()
                if (r.user.rol != "CONDUCTOR") {
                    error = "Esta app es para conductores. Los garajes se administran desde el portal web."
                } else {
                    sesion.guardar(r.access, r.refresh, r.user.nombre) // la navegación reacciona al guardar
                }
            } catch (e: Exception) {
                error = e.comoErrorDrivly().message
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
            Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Icon(Icons.Filled.LocalParking, contentDescription = null, Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(16.dp))
            Text("Drivly", style = MaterialTheme.typography.displaySmall)
            Text("Reservá tu lugar y pagá con Mercado Pago.", style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            Spacer(Modifier.height(40.dp))

            if (BuildConfig.GOOGLE_WEB_CLIENT_ID.isNotBlank()) {
                Button(
                    onClick = {
                        alcance.launch {
                            try {
                                pedirTokenDeGoogle(context)?.let(vm::conGoogle)
                            } catch (e: GetCredentialException) {
                                vm.mostrarError("No se pudo iniciar sesión con Google. Intentá nuevamente.")
                            } catch (e: GoogleIdTokenParsingException) {
                                vm.mostrarError("Google devolvió una respuesta inválida. Intentá nuevamente.")
                            }
                        }
                    },
                    enabled = !vm.cargando,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                ) { Text("Ingresar con Google") }
                Spacer(Modifier.height(12.dp))
            }
            if (BuildConfig.DEBUG) {
                OutlinedButton(onClick = vm::desarrollo, enabled = !vm.cargando,
                    modifier = Modifier.fillMaxWidth().height(56.dp)) {
                    Text("Acceso rápido de desarrollo")
                }
            }

            Spacer(Modifier.height(24.dp))
            if (vm.cargando) CircularProgressIndicator()
            vm.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
        }
    }
}

/** Credential Manager: devuelve el ID token de Google, o null si el usuario canceló. */
private suspend fun pedirTokenDeGoogle(context: Context): String? {
    val opcion = GetGoogleIdOption.Builder()
        .setServerClientId(BuildConfig.GOOGLE_WEB_CLIENT_ID) // el backend valida que el token sea para este client ID
        .setFilterByAuthorizedAccounts(false)
        .build()
    return try {
        val respuesta = CredentialManager.create(context)
            .getCredential(context, GetCredentialRequest.Builder().addCredentialOption(opcion).build())
        GoogleIdTokenCredential.createFrom(respuesta.credential.data).idToken
    } catch (e: GetCredentialCancellationException) {
        null // el usuario cerró el selector de cuentas
    }
}
