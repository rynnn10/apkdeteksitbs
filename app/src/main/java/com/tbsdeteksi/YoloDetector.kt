/* Updated: 2026-07-14 22:30 UTC | v2.1.0 | Native YOLOv8 TFLite detector */
package com.tbsdeteksi

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.util.Base64
import org.tensorflow.lite.Interpreter
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

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
        interpreter = Interpreter(ByteBuffer.wrap(model))
        android.util.Log.i("YOLO", "Model loaded: ${model.size} bytes")
        true
    } catch (e: Exception) {
        android.util.Log.e("YOLO", "Load failed: ${e.message}")
        false
    }

    fun detectFromBase64(base64: String): List<Detection> {
        val bytes = Base64.decode(base64, Base64.DEFAULT)
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return emptyList()
        return detect(bitmap)
    }

    fun detect(bitmap: Bitmap): List<Detection> {
        val interpreter = interpreter ?: return emptyList()

        // Preprocess: resize to 640x640, NCHW float32 [1,3,640,640]
        val resized = Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)
        val inputBytes = ByteBuffer.allocateDirect(1 * 3 * INPUT_SIZE * INPUT_SIZE * 4)
        inputBytes.order(ByteOrder.nativeOrder())

        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        resized.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)

        val mean = floatArrayOf(0.0f, 0.0f, 0.0f)
        val std = floatArrayOf(255.0f, 255.0f, 255.0f)

        for (i in pixels.indices) {
            val p = pixels[i]
            val r = ((p shr 16) and 0xFF).toFloat()
            val g = ((p shr 8) and 0xFF).toFloat()
            val b = (p and 0xFF).toFloat()
            // NCHW: channel, height*width
            inputBytes.putFloat((r - mean[0]) / std[0])
            inputBytes.putFloat((g - mean[1]) / std[1])
            inputBytes.putFloat((b - mean[2]) / std[2])
        }
        inputBytes.rewind()

        // Run inference — output [1, 10, 8400]
        val output = Array(1) { Array(10) { FloatArray(8400) } }
        interpreter.run(inputBytes, output)

        return postprocess(output[0])
    }

    private fun postprocess(raw: Array<FloatArray>): List<Detection> {
        val detections = mutableListOf<Detection>()
        val NUM_DETS = 8400

        for (i in 0 until NUM_DETS) {
            val cx = raw[0][i]
            val cy = raw[1][i]
            val w = raw[2][i]
            val h = raw[3][i]

            // Find best class
            var maxScore = -1f
            var bestClass = -1
            for (c in 0 until NUM_CLASSES) {
                val score = sigmoid(raw[4 + c][i])
                if (score > maxScore) {
                    maxScore = score
                    bestClass = c
                }
            }

            if (maxScore < CONF_THRESHOLD) continue

            // Convert cx,cy,w,h from grid space to normalized [0,1]
            // YOLOv8 raw output is already scaled to input dimensions
            val x1 = ((cx - w / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val y1 = ((cy - h / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val x2 = ((cx + w / 2) / INPUT_SIZE).coerceIn(0f, 1f)
            val y2 = ((cy + h / 2) / INPUT_SIZE).coerceIn(0f, 1f)

            detections.add(Detection(x1, y1, x2, y2, maxScore, bestClass, labels[bestClass]))
        }

        // NMS
        detections.sortByDescending { it.confidence }
        return nms(detections)
    }

    private fun nms(dets: List<Detection>): List<Detection> {
        val kept = mutableListOf<Detection>()
        val removed = BooleanArray(dets.size)

        for (i in dets.indices) {
            if (removed[i]) continue
            kept.add(dets[i])
            for (j in i + 1 until dets.size) {
                if (!removed[j] && iou(dets[i], dets[j]) > IOU_THRESHOLD) {
                    removed[j] = true
                }
            }
        }
        return kept
    }

    private fun iou(a: Detection, b: Detection): Float {
        val ax1 = a.x1; val ay1 = a.y1; val ax2 = a.x2; val ay2 = a.y2
        val bx1 = b.x1; val by1 = b.y1; val bx2 = b.x2; val by2 = b.y2
        val ix1 = maxOf(ax1, bx1); val iy1 = maxOf(ay1, by1)
        val ix2 = minOf(ax2, bx2); val iy2 = minOf(ay2, by2)
        val iw = maxOf(0f, ix2 - ix1); val ih = maxOf(0f, iy2 - iy1)
        val inter = iw * ih
        val areaA = (ax2 - ax1) * (ay2 - ay1)
        val areaB = (bx2 - bx1) * (by2 - by1)
        return inter / (areaA + areaB - inter)
    }

    private fun sigmoid(x: Float) = 1f / (1f + kotlin.math.exp(-x))

    fun close() {
        interpreter?.close()
        interpreter = null
    }
}
