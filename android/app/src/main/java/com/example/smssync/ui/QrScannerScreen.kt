package com.example.smssync.ui

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.smssync.data.PairingInfo
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Full-screen QR code scanner using CameraX + ML Kit Barcode Scanning.
 *
 * Scans the QR code displayed by the PC app to obtain pairing information
 * (host, port, token).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QrScannerScreen(
    onQrScanned: (PairingInfo) -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    var hasCameraPermission by remember { mutableStateOf(false) }

    // Intercept system back gesture to go back to main screen instead of exiting
    androidx.activity.compose.BackHandler { onBack() }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
        if (!granted) {
            Toast.makeText(context, "需要相机权限才能扫描二维码", Toast.LENGTH_SHORT).show()
            onBack()
        }
    }

    LaunchedEffect(Unit) {
        when {
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED -> {
                hasCameraPermission = true
            }
            else -> {
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("扫描二维码") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (hasCameraPermission) {
                QrScannerView(
                    onQrCodeDetected = { rawValue ->
                        val info = parseQrData(rawValue)
                        if (info != null) {
                            onQrScanned(info)
                        }
                    },
                )

                // Scan overlay
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Surface(
                        modifier = Modifier.size(250.dp),
                        shape = MaterialTheme.shapes.medium,
                        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.1f),
                        border = ButtonDefaults.outlinedButtonBorder,
                    ) {}
                }

                // Bottom hint
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .align(Alignment.BottomCenter)
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        "将二维码对准框内即可自动扫描",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                    )
                }
            }
        }
    }
}

/**
 * Parse QR code data into PairingInfo.
 *
 * Expected format (JSON):
 * {"v":1,"host":"192.168.1.100","port":9876,"token":"abc...","name":"DESKTOP-XXX"}
 */
private fun parseQrData(raw: String): PairingInfo? {
    return try {
        val obj = JSONObject(raw)
        val version = obj.optInt("v", 0)
        if (version < 1) return null

        PairingInfo(
            host = obj.getString("host"),
            port = obj.optInt("port", 9876),
            token = obj.getString("token"),
            name = obj.optString("name", ""),
        )
    } catch (e: Exception) {
        // Maybe it's a plain WebSocket URL?
        if (raw.startsWith("ws://") || raw.startsWith("wss://")) {
            try {
                val url = java.net.URI(raw)
                val port = if (url.port > 0) url.port else 9876
                // Extract token from query if present
                val token = url.query?.split("&")
                    ?.find { it.startsWith("token=") }
                    ?.substringAfter("token=") ?: ""
                PairingInfo(
                    host = url.host ?: return null,
                    port = port,
                    token = token,
                )
            } catch (_: Exception) {
                null
            }
        } else null
    }
}

@Composable
private fun QrScannerView(onQrCodeDetected: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            PreviewView(ctx).also { previewView ->
                val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                cameraProviderFuture.addListener({
                    val cameraProvider = cameraProviderFuture.get()

                    val preview = Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }

                    val imageAnalysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()
                        .also { analysis ->
                            val executor = Executors.newSingleThreadExecutor()
                            val scanner = BarcodeScanning.getClient()
                            analysis.setAnalyzer(executor) { imageProxy ->
                                @androidx.camera.core.ExperimentalGetImage
                                val mediaImage = imageProxy.image
                                if (mediaImage != null) {
                                    val image = InputImage.fromMediaImage(
                                        mediaImage, imageProxy.imageInfo.rotationDegrees
                                    )
                                    scanner.process(image)
                                        .addOnSuccessListener { barcodes ->
                                            for (barcode in barcodes) {
                                                if (barcode.valueType == Barcode.TYPE_TEXT) {
                                                    val value = barcode.rawValue ?: barcode.displayValue ?: continue
                                                    Log.d("QrScanner", "Detected: $value")
                                                    onQrCodeDetected(value)
                                                }
                                            }
                                        }
                                        .addOnCompleteListener {
                                            imageProxy.close()
                                        }
                                } else {
                                    imageProxy.close()
                                }
                            }
                        }

                    try {
                        cameraProvider.unbindAll()
                        cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            imageAnalysis,
                        )
                    } catch (e: Exception) {
                        Log.e("QrScanner", "Camera bind failed", e)
                    }
                }, ContextCompat.getMainExecutor(ctx))
            }
        },
    )
}
