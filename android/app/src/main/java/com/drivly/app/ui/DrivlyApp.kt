package com.drivly.app.ui

import android.net.Uri
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ConfirmationNumber
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.outlined.ConfirmationNumber
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.drivly.app.DrivlyApplication
import com.drivly.app.ui.buscar.BuscarScreen
import com.drivly.app.ui.login.LoginScreen
import com.drivly.app.ui.pago.PagoResultadoScreen
import com.drivly.app.ui.perfil.PerfilScreen
import com.drivly.app.ui.reservar.ReservarScreen
import com.drivly.app.ui.reservas.MisReservasScreen
import com.drivly.app.ui.ticket.TicketScreen
import kotlinx.coroutines.flow.StateFlow
import java.time.OffsetDateTime

private object Rutas {
    const val BUSCAR = "buscar"
    const val RESERVAS = "reservas"
    const val PERFIL = "perfil"
    const val RESERVAR = "reservar/{garajeId}?nombre={nombre}&direccion={direccion}&inicio={inicio}&fin={fin}"
    const val PAGO = "pago/{reservaId}?estado={estado}"
    const val TICKET = "ticket/{reservaId}"

    fun reservar(garajeId: String, nombre: String, direccion: String, inicio: OffsetDateTime, fin: OffsetDateTime) =
        "reservar/$garajeId?nombre=${Uri.encode(nombre)}&direccion=${Uri.encode(direccion)}" +
            "&inicio=${Uri.encode(inicio.toString())}&fin=${Uri.encode(fin.toString())}"

    fun pago(reservaId: String, estado: String?) = "pago/$reservaId?estado=${Uri.encode(estado.orEmpty())}"
    fun ticket(reservaId: String) = "ticket/$reservaId"
}

private data class Pestania(val ruta: String, val titulo: String, val icono: ImageVector, val iconoElegido: ImageVector)

private val PESTANIAS = listOf(
    Pestania(Rutas.BUSCAR, "Buscar", Icons.Outlined.Map, Icons.Filled.Map),
    Pestania(Rutas.RESERVAS, "Mis reservas", Icons.Outlined.ConfirmationNumber, Icons.Filled.ConfirmationNumber),
    Pestania(Rutas.PERFIL, "Perfil", Icons.Outlined.Person, Icons.Filled.Person),
)

/**
 * Navegación de la app. `deepLinks` trae drivly://pago-resultado?... cuando Mercado Pago vuelve a la app.
 */
@Composable
fun DrivlyApp(deepLinks: StateFlow<Uri?>, alConsumirDeepLink: () -> Unit) {
    val app = LocalContext.current.applicationContext as DrivlyApplication
    val logueado by app.sesion.logueado.collectAsStateWithLifecycle(initialValue = null)

    when (logueado) {
        null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        false -> LoginScreen()
        true -> AppLogueada(deepLinks, alConsumirDeepLink)
    }
}

@Composable
private fun AppLogueada(deepLinks: StateFlow<Uri?>, alConsumirDeepLink: () -> Unit) {
    val nav = rememberNavController()
    val deepLink by deepLinks.collectAsStateWithLifecycle()
    var mensaje by remember { mutableStateOf<String?>(null) }
    val actual by nav.currentBackStackEntryAsState()
    val rutaActual = actual?.destination?.route

    Scaffold(
        bottomBar = {
            // Sólo en las pestañas principales; reservar, pagar y el ticket usan toda la pantalla
            if (PESTANIAS.any { it.ruta == rutaActual }) {
                NavigationBar {
                    PESTANIAS.forEach { p ->
                        val elegida = p.ruta == rutaActual
                        NavigationBarItem(
                            selected = elegida,
                            onClick = { nav.irAPestania(p.ruta) },
                            icon = { Icon(if (elegida) p.iconoElegido else p.icono, contentDescription = null) },
                            label = { Text(p.titulo) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        // Cada pantalla tiene su propio Scaffold: acá sólo se reserva el espacio de la barra inferior
        NavHost(nav, startDestination = Rutas.BUSCAR, modifier = Modifier.padding(bottom = padding.calculateBottomPadding())) {
            composable(Rutas.BUSCAR) {
                BuscarScreen(
                    alElegir = { g, h -> nav.navigate(Rutas.reservar(g.id, g.nombre, g.direccion, h.inicio, h.fin)) },
                    mensaje = mensaje,
                    alMostrarMensaje = { mensaje = null },
                )
            }
            composable(Rutas.RESERVAS) { MisReservasScreen(alAbrirTicket = { id -> nav.navigate(Rutas.ticket(id)) }) }
            composable(Rutas.PERFIL) { PerfilScreen() }
            composable(Rutas.RESERVAR) { e ->
                val a = e.arguments!!
                ReservarScreen(
                    garajeId = a.getString("garajeId")!!,
                    nombre = a.getString("nombre").orEmpty(),
                    direccion = a.getString("direccion").orEmpty(),
                    inicio = OffsetDateTime.parse(a.getString("inicio")),
                    fin = OffsetDateTime.parse(a.getString("fin")),
                    alVolver = { nav.popBackStack() },
                    alConfirmarSinPago = { id -> nav.irAlTicket(id) },
                )
            }
            composable(Rutas.PAGO) { e ->
                PagoResultadoScreen(
                    reservaId = e.arguments!!.getString("reservaId")!!,
                    estadoMp = e.arguments!!.getString("estado")?.ifBlank { null },
                    alConfirmar = { id -> nav.irAlTicket(id) },
                    alVolver = { nav.popBackStack() },
                )
            }
            composable(Rutas.TICKET) { e ->
                TicketScreen(
                    reservaId = e.arguments!!.getString("reservaId")!!,
                    alVolver = { aviso ->
                        if (aviso != null) {
                            // Cancelada: se vuelve a Buscar con el aviso del reembolso
                            mensaje = aviso
                            nav.popBackStack(Rutas.BUSCAR, inclusive = false)
                        } else {
                            nav.popBackStack()
                        }
                    },
                )
            }
        }
    }

    // Mercado Pago volvió a la app: drivly://pago-resultado?collection_status=approved&external_reference=<id>
    LaunchedEffect(deepLink) {
        val uri = deepLink ?: return@LaunchedEffect
        val reservaId = uri.getQueryParameter("external_reference")
        if (reservaId != null) {
            val estado = uri.getQueryParameter("collection_status") ?: uri.getQueryParameter("mp_status")
            nav.navigate(Rutas.pago(reservaId, estado))
        }
        alConsumirDeepLink()
    }
}

/** Patrón estándar de NavigationBar: una sola copia de cada pestaña y se conserva su estado. */
private fun NavHostController.irAPestania(ruta: String) = navigate(ruta) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}

/** Al confirmarse la reserva se muestra el ticket y se saca del historial la pantalla de reservar/pago. */
private fun NavHostController.irAlTicket(reservaId: String) = navigate(Rutas.ticket(reservaId)) {
    popUpTo(Rutas.BUSCAR) { inclusive = false }
}
