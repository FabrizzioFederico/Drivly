package com.drivly.app.ui.components

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.drivly.app.data.descargarImagen
import com.drivly.app.data.urlDeMedia

/**
 * Foto del frente del garaje, a todo el ancho de la tarjeta. Si el garaje no cargó foto, o no se pudo bajar
 * (por ejemplo sin señal en el ticket), no ocupa lugar: la tarjeta queda como antes.
 */
@Composable
fun FotoGaraje(ruta: String?, nombre: String, alto: Dp = 120.dp) {
    val url = urlDeMedia(ruta)
    val imagen by produceState<Bitmap?>(null, url) { value = url?.let { descargarImagen(it) } }
    imagen?.let {
        Image(it.asImageBitmap(), contentDescription = "Foto de $nombre", contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxWidth().height(alto))
    }
}
