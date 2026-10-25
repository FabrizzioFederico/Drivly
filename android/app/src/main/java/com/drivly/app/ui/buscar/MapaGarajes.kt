package com.drivly.app.ui.buscar

import android.graphics.Color
import android.graphics.RectF
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.drivly.app.data.Posicion
import com.drivly.app.data.api.GarajeDisponible
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression.color
import org.maplibre.android.style.expressions.Expression.get
import org.maplibre.android.style.expressions.Expression.literal
import org.maplibre.android.style.expressions.Expression.switchCase
import org.maplibre.android.style.expressions.Expression.toBool
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.PropertyFactory.circleColor
import org.maplibre.android.style.layers.PropertyFactory.circleOpacity
import org.maplibre.android.style.layers.PropertyFactory.circleRadius
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeColor
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeWidth
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point

/**
 * Estilos vectoriales de OpenFreeMap (datos de OpenStreetMap, sin API key): "positron" en modo claro y "dark"
 * en modo oscuro, neutros para que se destaquen los puntos de Drivly. openstreetmap.org no admite apps.
 */
private const val ESTILO_CLARO = "https://tiles.openfreemap.org/styles/positron"
private const val ESTILO_OSCURO = "https://tiles.openfreemap.org/styles/dark"
private const val ZOOM = 14.5

private const val FUENTE_GARAJES = "garajes"
private const val CAPA_GARAJES = "garajes-capa"
private const val FUENTE_YO = "yo"

// Mismos colores que el tema (Brand, Debt, Action): MapLibre los pide como enteros de Android
private val AZUL = Color.parseColor("#0066FF")
private val ROJO = Color.parseColor("#FF5252")
private val VERDE = Color.parseColor("#00E6A7")

/** Mapa con los garajes (azul con lugar, rojo lleno) y la posición del conductor (verde). */
@Composable
fun MapaGarajes(
    posicion: Posicion,
    garajes: List<GarajeDisponible>,
    elegido: String?,
    alElegir: (String) -> Unit,
    modifier: Modifier = Modifier,
    /** Lo que tapan otros elementos sobre el mapa (tarjeta de horario arriba, hoja de garajes abajo). */
    margenSuperior: Dp = 0.dp,
    margenInferior: Dp = 0.dp,
    margenDerecho: Dp = 0.dp,
) {
    val context = LocalContext.current
    // MapLibre se inicializa recién acá (carga su librería nativa): hacerlo al abrir la app demoraba el arranque
    val vista = remember {
        MapLibre.getInstance(context)
        MapView(context).apply { onCreate(null) }
    }
    var mapa by remember { mutableStateOf<MapLibreMap?>(null) }
    var estilo by remember { mutableStateOf<Style?>(null) }
    val alElegirActual by rememberUpdatedState(alElegir)
    // Sigue el modo oscuro del teléfono, igual que el resto de la app
    val urlEstilo = if (isSystemInDarkTheme()) ESTILO_OSCURO else ESTILO_CLARO

    CicloDeVida(vista)

    AndroidView(
        modifier = modifier,
        factory = {
            vista.also { v ->
                v.getMapAsync { m ->
                    m.uiSettings.isRotateGesturesEnabled = false
                    m.uiSettings.isTiltGesturesEnabled = false
                    m.cameraPosition = CameraPosition.Builder().target(LatLng(posicion.lat, posicion.lng)).zoom(ZOOM).build()
                    m.addOnMapClickListener { punto ->
                        // Zona táctil de 48 dp alrededor del dedo: los puntos del mapa son chicos
                        val p = m.projection.toScreenLocation(punto)
                        val radio = 24 * v.resources.displayMetrics.density
                        val tocado = m.queryRenderedFeatures(RectF(p.x - radio, p.y - radio, p.x + radio, p.y + radio), CAPA_GARAJES)
                            .firstOrNull()?.getStringProperty("id")
                        tocado?.let(alElegirActual)
                        tocado != null
                    }
                    mapa = m
                }
            }
        },
    )

    // Estilo según el tema; al cambiarlo se vuelven a crear las capas y el efecto de abajo recarga los datos
    LaunchedEffect(mapa, urlEstilo) {
        val m = mapa ?: return@LaunchedEffect
        estilo = null
        m.setStyle(Style.Builder().fromUri(urlEstilo)) { s ->
            agregarCapas(s)
            estilo = s
        }
    }

    // Datos -> fuentes GeoJSON del estilo
    LaunchedEffect(estilo, garajes, elegido, posicion) {
        val s = estilo ?: return@LaunchedEffect
        s.getSourceAs<GeoJsonSource>(FUENTE_GARAJES)?.setGeoJson(FeatureCollection.fromFeatures(garajes.map { g ->
            Feature.fromGeometry(Point.fromLngLat(g.lng.toDouble(), g.lat.toDouble())).apply {
                addStringProperty("id", g.id)
                addBooleanProperty("lleno", g.lugaresLibres <= 0)
                addBooleanProperty("elegido", g.id == elegido)
            }
        }))
        // El punto verde sólo aparece con la ubicación real, no con la de respaldo (Palermo)
        val yo = if (posicion.esReal) listOf(Feature.fromGeometry(Point.fromLngLat(posicion.lng, posicion.lat))) else emptyList()
        s.getSourceAs<GeoJsonSource>(FUENTE_YO)?.setGeoJson(FeatureCollection.fromFeatures(yo))
    }

    // Al cambiar la búsqueda, la cámara encuadra al conductor y a todos los garajes (el radio es de 1 km)
    LaunchedEffect(mapa, posicion, garajes) {
        val m = mapa ?: return@LaunchedEffect
        if (garajes.isEmpty()) {
            m.animateCamera(CameraUpdateFactory.newLatLngZoom(LatLng(posicion.lat, posicion.lng), ZOOM))
        } else {
            val limites = LatLngBounds.Builder().include(LatLng(posicion.lat, posicion.lng))
            garajes.forEach { limites.include(LatLng(it.lat.toDouble(), it.lng.toDouble())) }
            val d = context.resources.displayMetrics.density
            val margen = (48 * d).toInt()
            m.animateCamera(CameraUpdateFactory.newLatLngBounds(
                limites.build(), margen, margen + (margenSuperior.value * d).toInt(),
                margen + (margenDerecho.value * d).toInt(), margen + (margenInferior.value * d).toInt(),
            ))
        }
    }
    LaunchedEffect(mapa, elegido) {
        val g = garajes.firstOrNull { it.id == elegido } ?: return@LaunchedEffect
        mapa?.animateCamera(CameraUpdateFactory.newLatLng(LatLng(g.lat.toDouble(), g.lng.toDouble())))
    }
}

private fun agregarCapas(s: Style) {
    s.addSource(GeoJsonSource(FUENTE_YO))
    s.addLayer(CircleLayer("yo-halo", FUENTE_YO).withProperties(circleRadius(18f), circleColor(VERDE), circleOpacity(0.25f)))
    s.addLayer(CircleLayer("yo-punto", FUENTE_YO).withProperties(
        circleRadius(7f), circleColor(VERDE), circleStrokeColor(Color.WHITE), circleStrokeWidth(3f),
    ))
    s.addSource(GeoJsonSource(FUENTE_GARAJES))
    s.addLayer(CircleLayer(CAPA_GARAJES, FUENTE_GARAJES).withProperties(
        circleRadius(switchCase(toBool(get("elegido")), literal(12f), literal(8f))),
        circleColor(switchCase(toBool(get("lleno")), color(ROJO), color(AZUL))),
        circleStrokeColor(Color.WHITE),
        circleStrokeWidth(switchCase(toBool(get("elegido")), literal(4f), literal(2f))),
    ))
}

/** MapView necesita los eventos de ciclo de vida de la pantalla (y destruirse al salir de la composición). */
@Composable
private fun CicloDeVida(vista: MapView) {
    val ciclo = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(ciclo, vista) {
        var ultimo = Lifecycle.Event.ON_CREATE
        val observador = LifecycleEventObserver { _, evento ->
            when (evento) {
                Lifecycle.Event.ON_START -> vista.onStart()
                Lifecycle.Event.ON_RESUME -> vista.onResume()
                Lifecycle.Event.ON_PAUSE -> vista.onPause()
                Lifecycle.Event.ON_STOP -> vista.onStop()
                else -> return@LifecycleEventObserver // ON_DESTROY se maneja en onDispose
            }
            ultimo = evento
        }
        ciclo.addObserver(observador)
        onDispose {
            ciclo.removeObserver(observador)
            if (ultimo == Lifecycle.Event.ON_RESUME) vista.onPause()
            if (ultimo == Lifecycle.Event.ON_RESUME || ultimo == Lifecycle.Event.ON_START) vista.onStop()
            vista.onDestroy()
        }
    }
}
