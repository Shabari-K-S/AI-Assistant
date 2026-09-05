package com.assistant.athena.data

import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import java.io.ByteArrayOutputStream

/**
 * In-memory holder and processor for system-level screen captures.
 * Enables Gemini-style screen context reasoning across AssistantOverlayActivity and SessionsChatScreen.
 */
object ScreenCaptureHolder {
    private const val TAG = "Athena.ScreenCapture"

    @Volatile
    private var lastBitmap: Bitmap? = null

    @Volatile
    private var capturedAtTimestamp: Long = 0L

    /**
     * Store a freshly captured screenshot from VoiceInteractionSession or MediaProjection.
     */
    fun setScreenshot(bitmap: Bitmap?) {
        if (bitmap == null) return
        try {
            // Recycle prior bitmap if distinct to avoid memory leak
            if (lastBitmap != null && lastBitmap != bitmap && !lastBitmap!!.isRecycled) {
                lastBitmap?.recycle()
            }
            lastBitmap = bitmap
            capturedAtTimestamp = System.currentTimeMillis()
            Log.i(TAG, "Screen context updated (${bitmap.width}x${bitmap.height}) at $capturedAtTimestamp")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to cache screenshot", e)
        }
    }

    /**
     * Returns true if there is a screen capture cached within the freshness threshold.
     */
    fun hasFreshScreenshot(maxAgeMs: Long = 90_000L): Boolean {
        val bmp = lastBitmap
        return bmp != null && !bmp.isRecycled && (System.currentTimeMillis() - capturedAtTimestamp) <= maxAgeMs
    }

    /**
     * Retrieve the cached screenshot if fresh.
     */
    fun getScreenshot(maxAgeMs: Long = 90_000L): Bitmap? {
        return if (hasFreshScreenshot(maxAgeMs)) lastBitmap else null
    }

    /**
     * Clear cached screenshot and reclaim memory.
     */
    fun clear() {
        try {
            if (lastBitmap != null && !lastBitmap!!.isRecycled) {
                lastBitmap?.recycle()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Error recycling bitmap", e)
        }
        lastBitmap = null
        capturedAtTimestamp = 0L
    }

    /**
     * Downscales and compresses the screenshot into a lightweight Base64 JPEG
     * optimized for Gemini Multimodal Vision API limits and fast upload latency.
     */
    fun toBase64Jpeg(bitmap: Bitmap? = lastBitmap, maxDim: Int = 1280, quality: Int = 85): String? {
        val src = bitmap ?: return null
        if (src.isRecycled) return null

        return try {
            val width = src.width
            val height = src.height
            val scale = if (width > maxDim || height > maxDim) {
                val ratio = width.toFloat() / height.toFloat()
                if (ratio > 1f) {
                    maxDim.toFloat() / width.toFloat()
                } else {
                    maxDim.toFloat() / height.toFloat()
                }
            } else {
                1f
            }

            val targetWidth = (width * scale).toInt().coerceAtLeast(1)
            val targetHeight = (height * scale).toInt().coerceAtLeast(1)

            val scaledBitmap = if (scale < 1f) {
                Bitmap.createScaledBitmap(src, targetWidth, targetHeight, true)
            } else {
                src
            }

            val baos = ByteArrayOutputStream()
            scaledBitmap.compress(Bitmap.CompressFormat.JPEG, quality, baos)
            val bytes = baos.toByteArray()

            if (scaledBitmap != src && !scaledBitmap.isRecycled) {
                scaledBitmap.recycle()
            }

            Base64.encodeToString(bytes, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to encode screenshot to Base64 JPEG", e)
            null
        }
    }
}
