/* Updated: 2026-07-15 00:00 UTC | v2.2.0 | Native YOLO TFLite (LiteRT) offline */
package com.tbsdeteksi

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.tensorflow.lite.Interpreter
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class YoloDetector(private val context: Context) {
    private var interpreter: Interpreter? = null

    val labels = listOf("Janjang kosong", "Kurang masak", "TBS abnormal", "TBS masak", "TBS mentah", "Terlalu masak")
    private val INPUT_SIZE = 640
    private val CONF_THRESHOLD = 0.25f
    private val IOU_THRESHOLD = 0.45f
    private val NUM_CLASSES = 6

    data class Detection(
        val x1: Float, val y1: Float, val x2: Float, val y2: Float,
        val confidence: Float, val classIndex: Int, val className: String
    )

    fun load(): Boolean = try {
        val model = context.assets.open("best.tflite").use { it.readBytes() }
        android.util.Log.i("YOLO", "Read ${model.size} bytes")
        val cacheFile = File(context.cacheDir, "yolo_model_${model.size}.tflite")
        if (!cacheFile.exists()) cacheFile.writeBytes(model)
        interpreter = Interpreter(cacheFile)
        android.util.Log.i("YOLO", "Model loaded OK")
        true
    } catch (e: Exception) {
        android.util.Log.e("YOLO", "Load failed", e)
        false
    }

    fun detectFromBase64(base64: String): List<Detection> = try {
        val bytes = android.util.Base64.decode(base64, android.util.Base64.DEFAULT)
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return emptyList()
        detect(bitmap)
    } catch (e: Exception) {
        android.util.Log.e("YOLO", "detectFromBase64 failed", e)
        emptyList()
    }

    fun detect(bitmap: Bitmap): List<Detection> {
        val interpreter = interpreter ?: return emptyList()
        val resized = Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)
        val inputBytes = ByteBuffer.allocateDirect(1 * 3 * INPUT_SIZE * INPUT_SIZE * 4)
        inputBytes.order(ByteOrder.nativeOrder())
        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        resized.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)
        // NCHW: all R, then all G, then all B
        for (i in pixels.indices) inputBytes.putFloat(((pixels[i] shr 16) and 0xFF).toFloat() / 255f)
        for (i in pixels.indices) inputBytes.putFloat(((pixels[i] shr 8) and 0xFF).toFloat() / 255f)
        for (i in pixels.indices) inputBytes.putFloat((pixels[i] and 0xFF).toFloat() / 255f)
        inputBytes.rewind()

        val output = Array(1) { Array(10) { FloatArray(8400) } }
        interpreter.run(inputBytes, output)
        return postprocess(output[0])
    }

    private fun postprocess(raw: Array<FloatArray>): List<Detection> {
        val dets = mutableListOf<Detection>()
        for (i in 0 until 8400) {
            val cx = raw[0][i]; val cy = raw[1][i]; val w = raw[2][i]; val h = raw[3][i]
            var maxScore = -1f; var bestClass = -1
            for (c in 0 until NUM_CLASSES) {
                val score = 1f / (1f + kotlin.math.exp(-raw[4 + c][i]))
                if (score > maxScore) { maxScore = score; bestClass = c }
            }
            if (maxScore < CONF_THRESHOLD) continue
            val x1 = ((cx - w / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val y1 = ((cy - h / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val x2 = ((cx + w / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val y2 = ((cy + h / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            dets.add(Detection(x1, y1, x2, y2, maxScore, bestClass, labels[bestClass]))
        }
        dets.sortByDescending { it.confidence }
        return nms(dets)
    }

    private fun nms(dets: List<Detection>): List<Detection> {
        val kept = mutableListOf<Detection>()
        val removed = BooleanArray(dets.size)
        for (i in dets.indices) {
            if (removed[i]) continue
            kept.add(dets[i])
            for (j in i + 1 until dets.size) {
                if (!removed[j] && iou(dets[i], dets[j]) > IOU_THRESHOLD) removed[j] = true
            }
        }
        return kept
    }

    private fun iou(a: Detection, b: Detection): Float {
        val ix = maxOf(a.x1, b.x1); val iy = maxOf(a.y1, b.y1)
        val iw = maxOf(0f, minOf(a.x2, b.x2) - ix); val ih = maxOf(0f, minOf(a.y2, b.y2) - iy)
        val inter = iw * ih
        return inter / ((a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter)
    }

    fun close() { interpreter?.close(); interpreter = null }
}
