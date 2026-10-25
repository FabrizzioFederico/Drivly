package com.drivly.app.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import com.drivly.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.net.URI

private const val LADO_MAXIMO = 1024 // el servidor la deja en 512: subir más es gastar datos

/** https://dominio/api/ -> https://dominio (las fotos llegan como /api/media/...). */
private val origen: String = URI(BuildConfig.API_URL).let { u ->
    "${u.scheme}://${u.host}${if (u.port != -1) ":${u.port}" else ""}"
}

fun urlDeMedia(ruta: String?): String? = ruta?.let { if (it.startsWith("http")) it else origen + it }

/**
 * Foto elegida por el usuario -> JPEG de hasta 1024 px listo para subir (unos 200 KB en lugar de varios MB).
 * ImageDecoder (Android 9+) ya aplica la rotación EXIF de la cámara al decodificar.
 */
suspend fun fotoParaSubir(context: Context, uri: Uri): MultipartBody.Part = withContext(Dispatchers.IO) {
    val bitmap = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri)) { decoder, info, _ ->
            val escala = LADO_MAXIMO.toFloat() / maxOf(info.size.width, info.size.height)
            if (escala < 1f) decoder.setTargetSize((info.size.width * escala).toInt(), (info.size.height * escala).toInt())
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
        }
    } else {
        // Android 8: muestreo por potencias de 2 (la rotación EXIF puede no aplicarse)
        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)!!.use { BitmapFactory.decodeStream(it, null, limites) }
        var muestra = 1
        while (maxOf(limites.outWidth, limites.outHeight) / (muestra * 2) >= LADO_MAXIMO) muestra *= 2
        context.contentResolver.openInputStream(uri)!!.use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = muestra })!!
        }
    }
    val bytes = ByteArrayOutputStream().use { salida ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 85, salida)
        salida.toByteArray()
    }
    MultipartBody.Part.createFormData("foto", "foto.jpg", bytes.toRequestBody("image/jpeg".toMediaType()))
}

private val clienteImagenes = OkHttpClient()

/** Descarga una imagen chica (la foto de perfil, 512 px). La URL cambia en cada subida: no hay caché vieja. */
suspend fun descargarImagen(url: String): Bitmap? = withContext(Dispatchers.IO) {
    runCatching {
        clienteImagenes.newCall(Request.Builder().url(url).header("ngrok-skip-browser-warning", "1").build()).execute()
            .use { r -> if (r.isSuccessful) r.body?.byteStream()?.use(BitmapFactory::decodeStream) else null }
    }.getOrNull()
}
