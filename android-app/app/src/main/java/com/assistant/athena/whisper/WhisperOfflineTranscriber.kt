package com.assistant.athena.whisper

import android.content.Context
import android.util.Log
import com.whispertflite.asr.Whisper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.util.concurrent.atomic.AtomicBoolean

/**
 * On-Device Offline OpenAI Whisper Transcriber using TFLite.
 * Runs completely locally on Android without internet connectivity or cloud costs.
 */
object WhisperOfflineTranscriber {
    private const val TAG = "WhisperOffline"
    private const val MODEL_ASSET = "whisper-tiny.tflite"
    private const val VOCAB_ASSET = "filters_vocab_multilingual.bin"

    private var whisper: Whisper? = null
    private val isInitializing = AtomicBoolean(false)
    private val isReady = AtomicBoolean(false)

    fun isLoaded(): Boolean = isReady.get()

    /**
     * Initializes the Whisper TFLite model in the background.
     */
    suspend fun initialize(context: Context): Boolean = withContext(Dispatchers.IO) {
        if (isReady.get()) return@withContext true
        if (isInitializing.getAndSet(true)) return@withContext false

        try {
            val modelFile = copyAssetToInternalStorage(context, MODEL_ASSET)
            val vocabFile = copyAssetToInternalStorage(context, VOCAB_ASSET)

            if (modelFile.exists() && vocabFile.exists()) {
                val whisperInstance = Whisper(context.applicationContext)
                whisperInstance.loadModel(modelFile.absolutePath, vocabFile.absolutePath, true)
                whisperInstance.setAction(Whisper.ACTION_TRANSCRIBE)
                whisper = whisperInstance
                isReady.set(true)
                Log.i(TAG, "On-device Whisper TFLite initialized successfully (${modelFile.length() / (1024 * 1024)}MB)")
                return@withContext true
            } else {
                Log.e(TAG, "Failed to locate model or vocab files after extraction")
                return@withContext false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error initializing on-device Whisper", e)
            return@withContext false
        } finally {
            isInitializing.set(false)
        }
    }

    /**
     * Transcribes a 16kHz WAV byte array on-device using Whisper TFLite.
     */
    suspend fun transcribeAudio(context: Context, wavBytes: ByteArray): String = withContext(Dispatchers.IO) {
        if (!isReady.get()) {
            val ok = initialize(context)
            if (!ok) return@withContext ""
        }

        try {
            val tempWav = File(context.cacheDir, "whisper_temp_${System.currentTimeMillis()}.wav")
            tempWav.writeBytes(wavBytes)

            val result = suspendTranscribeFile(tempWav)
            tempWav.delete()
            return@withContext result
        } catch (e: Exception) {
            Log.e(TAG, "On-device Whisper transcription failed", e)
            return@withContext ""
        }
    }

    private suspend fun suspendTranscribeFile(file: File): String = withContext(Dispatchers.IO) {
        val instance = whisper ?: return@withContext ""
        var transcribedText = ""
        val lock = Object()

        instance.setListener(object : Whisper.WhisperListener {
            override fun onUpdateReceived(message: String?) {
                Log.d(TAG, "Whisper status: $message")
            }

            override fun onResultReceived(result: String?) {
                transcribedText = result?.trim() ?: ""
                synchronized(lock) {
                    lock.notifyAll()
                }
            }
        })

        instance.setFilePath(file.absolutePath)
        instance.start()

        synchronized(lock) {
            lock.wait(15000L) // Wait up to 15s for inference
        }

        return@withContext transcribedText
    }

    private fun copyAssetToInternalStorage(context: Context, assetName: String): File {
        val outFile = File(context.filesDir, assetName)
        if (outFile.exists() && outFile.length() > 1000L) {
            return outFile
        }

        context.assets.open(assetName).use { input: InputStream ->
            FileOutputStream(outFile).use { output: FileOutputStream ->
                val buffer = ByteArray(8192)
                var read: Int
                while (input.read(buffer).also { read = it } != -1) {
                    output.write(buffer, 0, read)
                }
                output.flush()
            }
        }
        return outFile
    }
}
