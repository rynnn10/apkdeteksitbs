/* Updated: 2026-07-14 22:30 UTC | v2.1.0 | Native YOLO TFLite + JS bridge + back button fix */
package com.tbsdeteksi

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.webkit.*
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.OnBackPressedCallback
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.tbsdeteksi.ui.theme.TBSDeteksiTheme
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream

class MainActivity : ComponentActivity() {
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null
    private var yoloDetector: YoloDetector? = null

    private val cameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            Toast.makeText(this, "Izin kamera diperlukan untuk fitur foto", Toast.LENGTH_SHORT).show()
        }
    }

    private val locationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            Toast.makeText(this, "Izin lokasi diperlukan untuk GPS tagging", Toast.LENGTH_SHORT).show()
        }
    }

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        fileUploadCallback?.onReceiveValue(uri?.let { arrayOf(it) } ?: arrayOf())
        fileUploadCallback = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Request permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        // Back button with exit confirmation (OnBackPressedCallback, non-deprecated)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                AlertDialog.Builder(this@MainActivity)
                    .setTitle("Keluar Aplikasi")
                    .setMessage("Yakin ingin keluar dari TBS Deteksi?")
                    .setPositiveButton("Ya") { _, _ -> finish() }
                    .setNegativeButton("Batal", null)
                    .show()
            }
        })

        // Load YOLO TFLite model
        yoloDetector = YoloDetector(this)
        nativeDetectorReady = yoloDetector?.load() ?: false
        if (!nativeDetectorReady) {
            Toast.makeText(this, "Gagal load model YOLO", Toast.LENGTH_LONG).show()
        }

        setContent {
            TBSDeteksiTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    WebViewScreen()
                }
            }
        }
    }

    private var nativeDetectorReady = false

    inner class NativeBridge {
        @JavascriptInterface
        fun isAvailable(): Boolean = nativeDetectorReady

        @JavascriptInterface
        fun detect(imageBase64: String): String = try {
            val detector = yoloDetector ?: return "[]"
            val detections = detector.detectFromBase64(imageBase64)
            val arr = JSONArray()
            for (d in detections) {
                val obj = JSONObject()
                val bbox = JSONObject()
                bbox.put("x1", d.x1.toDouble())
                bbox.put("y1", d.y1.toDouble())
                bbox.put("x2", d.x2.toDouble())
                bbox.put("y2", d.y2.toDouble())
                obj.put("bbox", bbox)
                // ponytail: map Roboflow names to internal names
                obj.put("kelas_pred", resolveKelas(d.className))
                obj.put("confidence", String.format("%.2f", d.confidence * 100).toFloat())
                obj.put("kelas_en", kelasEn(d.className))
                obj.put("rekomendasi", rekomendasi(d.className))
                obj.put("warna", warna(d.className))
                arr.put(obj)
            }
            return arr.toString()
        } catch (e: Exception) {
            android.util.Log.e("NativeBridge", "detect failed", e)
            "[]"
        }
    }

    private val KELAS_MAP = mapOf(
        "Janjang kosong" to "busuk", "TBS abnormal" to "busuk",
        "Kurang masak" to "kurang_matang", "TBS masak" to "matang",
        "TBS mentah" to "mentah", "Terlalu masak" to "terlalu_matang"
    )

    private val KELAS_EN = mapOf(
        "Janjang kosong" to "Empty Bunch", "TBS abnormal" to "Abnormal",
        "Kurang masak" to "Underripe", "TBS masak" to "Ripe",
        "TBS mentah" to "Unripe", "Terlalu masak" to "Overripe"
    )

    private val REKOMENDASI = mapOf(
        "Janjang kosong" to "Tolak! TBS busuk/abnormal, tidak layak olah.",
        "TBS abnormal" to "Tolak! TBS busuk/abnormal, tidak layak olah.",
        "Kurang masak" to "Belum optimal. Tunggu 3-5 hari lagi.",
        "TBS masak" to "Layak panen! Kematangan optimal.",
        "TBS mentah" to "Tidak layak panen. Tunggu 7-10 hari lagi.",
        "Terlalu masak" to "Terlalu matang. Segera panen/reject jika brondolan >25%."
    )

    private val WARNA = mapOf(
        "Janjang kosong" to "#6B21A8", "TBS abnormal" to "#6B21A8",
        "Kurang masak" to "#D97706", "TBS masak" to "#16A34A",
        "TBS mentah" to "#DC2626", "Terlalu masak" to "#EA580C"
    )

    private fun resolveKelas(name: String) = KELAS_MAP[name] ?: name
    private fun kelasEn(name: String) = KELAS_EN[name] ?: name
    private fun rekomendasi(name: String) = REKOMENDASI[name] ?: ""
    private fun warna(name: String) = WARNA[name] ?: "#6B7280"

    @Composable
    fun WebViewScreen() {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                WebView(context).apply {
                    settings.apply {
                        javaScriptEnabled = true
                        domStorageEnabled = true
                        databaseEnabled = true
                        allowFileAccess = true
                        allowContentAccess = true
                        allowFileAccessFromFileURLs = true
                        allowUniversalAccessFromFileURLs = true
                        mediaPlaybackRequiresUserGesture = false
                        setSupportZoom(true)
                        builtInZoomControls = false
                        displayZoomControls = false
                    }

                    addJavascriptInterface(NativeBridge(), "NativeDetector")

                    webViewClient = object : WebViewClient() {
                        override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                            super.onReceivedError(view, request, error)
                            Toast.makeText(context, "Error: ${error?.description}", Toast.LENGTH_SHORT).show()
                        }

                        override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                            return false
                        }
                    }

                    webChromeClient = object : WebChromeClient() {
                        override fun onPermissionRequest(request: PermissionRequest?) {
                            request?.grant(request.resources)
                        }

                        override fun onShowFileChooser(
                            webView: WebView?,
                            filePathCallback: ValueCallback<Array<Uri>>?,
                            fileChooserParams: FileChooserParams?
                        ): Boolean {
                            fileUploadCallback?.onReceiveValue(null)
                            fileUploadCallback = filePathCallback
                            fileChooserLauncher.launch("image/*")
                            return true
                        }

                        override fun onGeolocationPermissionsShowPrompt(
                            origin: String?,
                            callback: GeolocationPermissions.Callback?
                        ) {
                            callback?.invoke(origin, true, false)
                        }
                    }

                    loadUrl("file:///android_asset/index.html")
                }
            }
        )
    }
}
