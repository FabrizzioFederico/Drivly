package com.drivly.app.ui.playero

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.UseCase
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.drivly.app.ui.theme.Action
import com.drivly.app.ui.theme.Ink900
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

private enum class EstadoCamara { LISTA, SIN_PERMISO, NO_DISPONIBLE }

/** Visor de cámara. Si no hay permiso o cámara, el playero usa el ingreso manual, igual que en la web. */
@Composable
fun VisorQr(activo: Boolean, alEscanear: (String) -> Unit, modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    val dueno = LocalLifecycleOwner.current
    val vista = remember { PreviewView(contexto) }
    val escanear by rememberUpdatedState(alEscanear)
    var permiso by remember { mutableStateOf(tienePermiso(contexto)) }
    var estado by remember { mutableStateOf(EstadoCamara.LISTA) }
    val pedirPermiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { concedido ->
        permiso = concedido
        estado = if (concedido) EstadoCamara.LISTA else EstadoCamara.SIN_PERMISO
    }

    LaunchedEffect(activo) { if (activo && !permiso) pedirPermiso.launch(Manifest.permission.CAMERA) }

    val encendida = activo && permiso
    if (encendida) {
        DisposableEffect(dueno) {
            val cierre = encenderCamara(contexto, dueno, vista, { escanear(it) }, { estado = EstadoCamara.NO_DISPONIBLE })
            onDispose(cierre)
        }
    }

    Box(modifier.fillMaxWidth().height(250.dp).clip(MaterialTheme.shapes.large).background(Ink900)) {
        if (encendida && estado == EstadoCamara.LISTA) AndroidView({ vista }, Modifier.fillMaxSize())
        Box(Modifier.align(Alignment.Center).size(150.dp).border(3.dp, Action, MaterialTheme.shapes.medium))
        Text(
            when {
                !activo -> "Elegí qué vas a escanear"
                estado == EstadoCamara.SIN_PERMISO -> "Sin permiso de cámara. Usá ingreso manual."
                estado == EstadoCamara.NO_DISPONIBLE -> "No se pudo abrir la cámara. Usá ingreso manual."
                else -> "Apuntá al QR del conductor"
            },
            color = Color.White, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(10.dp),
        )
    }
}

private fun tienePermiso(contexto: Context) =
    ContextCompat.checkSelfPermission(contexto, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

/** Enciende la cámara y devuelve cómo apagarla. Avisa una sola vez por encendido: después el visor se apaga. */
@OptIn(ExperimentalGetImage::class)
private fun encenderCamara(
    contexto: Context,
    dueno: LifecycleOwner,
    vista: PreviewView,
    alEscanear: (String) -> Unit,
    alFallar: () -> Unit,
): () -> Unit {
    val principal = ContextCompat.getMainExecutor(contexto)
    val analisis = Executors.newSingleThreadExecutor()
    val lector = BarcodeScanning.getClient(BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())
    val proveedorFuturo = ProcessCameraProvider.getInstance(contexto)
    var apagada = false
    var leido = false
    var casos: Array<UseCase> = emptyArray()

    proveedorFuturo.addListener({
        if (apagada) return@addListener
        try {
            val proveedor = proveedorFuturo.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(vista.surfaceProvider) }
            val imagenes = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            imagenes.setAnalyzer(analisis) { cuadro ->
                val imagen = cuadro.image
                if (imagen == null) {
                    cuadro.close()
                    return@setAnalyzer
                }
                lector.process(InputImage.fromMediaImage(imagen, cuadro.imageInfo.rotationDegrees))
                    .addOnSuccessListener(principal) { codigos ->
                        val valor = codigos.firstNotNullOfOrNull { it.rawValue }
                        if (valor != null && !leido && !apagada) {
                            leido = true
                            alEscanear(valor)
                        }
                    }
                    .addOnCompleteListener { cuadro.close() }
            }
            // Algunas tablets sólo tienen cámara frontal
            val camara = if (proveedor.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) CameraSelector.DEFAULT_BACK_CAMERA
            else CameraSelector.DEFAULT_FRONT_CAMERA
            casos = arrayOf(preview, imagenes)
            proveedor.bindToLifecycle(dueno, camara, *casos)
        } catch (e: Exception) {
            alFallar()
        }
    }, principal)

    return {
        apagada = true
        if (proveedorFuturo.isDone && casos.isNotEmpty()) proveedorFuturo.get().unbind(*casos)
        lector.close()
        analisis.shutdown()
    }
}
