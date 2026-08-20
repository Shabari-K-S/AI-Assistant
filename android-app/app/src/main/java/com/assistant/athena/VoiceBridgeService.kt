package com.assistant.athena

import android.annotation.SuppressLint
import android.app.*
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Base64
import android.util.Log
import androidx.core.app.NotificationCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import kotlin.math.abs

/**
 * A.T.H.E.N.A. — Adaptive Thinking Hands-free Engine for Neural Assistance
 *
 * ChatGPT-Style Continuous Voice Engine:
 *   - 100% Silent raw AudioRecord PCM stream (ZERO Google beeps/chimes).
 *   - Real-time Voice Activity Detection (VAD).
 *   - Sends speech chunks to Termux backend (/transcribe).
 *   - Audio output is spoken by Termux Python TTS.
 */
class VoiceBridgeService : Service() {

    companion object {
        private const val TAG = "Athena.Service"
        private const val CHANNEL_ID = "athena_voice_bridge"
        private const val NOTIFICATION_ID = 7001

        // Backend endpoints — Termux evbridge.py
        private const val BACKEND_BASE = "http://127.0.0.1:2027"
        private const val TRANSCRIBE_URL = "$BACKEND_BASE/transcribe"
        private const val STREAM_URL = "$BACKEND_BASE/stream"

        // State constants
        const val STATE_STANDBY = "standby"
        const val STATE_LISTENING = "listening"
        const val STATE_PROCESSING = "processing"
        const val STATE_SPEAKING = "speaking"
        const val STATE_ERROR = "error"

        var onLogListener: ((String) -> Unit)? = null
    }

    // --- Core components ---
    private var wakeLock: PowerManager.WakeLock? = null
    private val handler = Handler(Looper.getMainLooper())

    // --- AudioRecord VAD Engine ---
    private var audioRecord: AudioRecord? = null
    private var vadThread: Thread? = null
    private var isRecording = false
    private var isTermuxSpeaking = false
    private var isDestroyed = false

    // Audio config
    private val sampleRate = 16000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
    private val minBufferSize = maxOf(AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat), 4096)

    // --- Network ---
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()
    private var sseEventSource: EventSource? = null

    private fun broadcastLog(msg: String) {
        try {
            onLogListener?.invoke(msg)
        } catch (_: Exception) {}
    }

    private fun triggerHapticFeedback() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vm?.defaultVibrator?.vibrate(VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK))
            } else {
                @Suppress("DEPRECATION")
                val v = getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                @Suppress("DEPRECATION")
                v?.vibrate(40L)
            }
        } catch (_: Exception) {}
    }

    // =========================================================================
    // Service Lifecycle
    // =========================================================================

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "═══ A.T.H.E.N.A. Continuous Silent Voice Engine starting ═══")

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "Athena::VoiceBridgeWakeLock"
        ).apply {
            acquire(24 * 60 * 60 * 1000L)
        }

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification(STATE_LISTENING, "Continuous silent listening active..."))

        connectSSEStream()
        startVadListening()

        broadcastLog("🎙️ ChatGPT Continuous Voice Engine active (100% silent, 0 beeps)")
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge online ═══")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge shutting down ═══")
        isDestroyed = true

        stopVadListening()

        sseEventSource?.cancel()
        sseEventSource = null

        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // =========================================================================
    // Notification
    // =========================================================================

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "ATHENA Voice Bridge",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "24/7 continuous voice assistant bridge"
                setShowBadge(false)
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(state: String, detail: String): Notification {
        val icon = when (state) {
            STATE_LISTENING -> android.R.drawable.ic_btn_speak_now
            STATE_PROCESSING -> android.R.drawable.ic_popup_sync
            STATE_SPEAKING -> android.R.drawable.ic_lock_silent_mode_off
            STATE_ERROR -> android.R.drawable.ic_dialog_alert
            else -> android.R.drawable.ic_lock_silent_mode
        }

        val title = when (state) {
            STATE_LISTENING -> "🎙️ ATHENA — Continuous Listening (Silent)"
            STATE_PROCESSING -> "⚡ ATHENA — Thinking..."
            STATE_SPEAKING -> "🔊 ATHENA — Speaking (Termux)..."
            STATE_ERROR -> "⚠️ ATHENA — Error"
            else -> "🛡️ ATHENA — Ready"
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(detail)
            .setSmallIcon(icon)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun updateState(state: String, detail: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(state, detail))
    }

    // =========================================================================
    // Silent AudioRecord VAD Engine (ChatGPT Style)
    // =========================================================================

    @SuppressLint("MissingPermission")
    private fun startVadListening() {
        if (isRecording || isDestroyed) return

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                channelConfig,
                audioFormat,
                minBufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord failed to initialize")
                updateState(STATE_ERROR, "Microphone hardware busy")
                return
            }

            audioRecord?.startRecording()
            isRecording = true

            vadThread = Thread {
                val buffer = ShortArray(1024)
                val speechBuffer = ByteArrayOutputStream()
                var isSpeaking = false
                var silenceFrames = 0
                var speechFrames = 0
                var noiseFloor = 400.0

                while (isRecording && !isDestroyed) {
                    if (isTermuxSpeaking) {
                        // Sleep briefly while Termux is outputting speech to prevent echo loop
                        Thread.sleep(100)
                        continue
                    }

                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0) {
                        var sum = 0.0
                        for (i in 0 until read) {
                            sum += abs(buffer[i].toDouble())
                        }
                        val rms = sum / read

                        // Dynamic noise floor tracking
                        if (!isSpeaking) {
                            noiseFloor = noiseFloor * 0.96 + rms * 0.04
                        }

                        val speechThreshold = maxOf(noiseFloor * 2.0, 650.0)

                        if (rms > speechThreshold) {
                            silenceFrames = 0
                            speechFrames++
                            if (!isSpeaking && speechFrames >= 2) {
                                isSpeaking = true
                                speechBuffer.reset()
                                handler.post {
                                    updateState(STATE_LISTENING, "Hearing your voice...")
                                }
                            }
                        } else {
                            if (isSpeaking) {
                                silenceFrames++
                                // ~0.8 second of silence after speaking -> turn complete!
                                if (silenceFrames >= 12) {
                                    isSpeaking = false
                                    speechFrames = 0
                                    val pcmData = speechBuffer.toByteArray()
                                    speechBuffer.reset()

                                    // Process if audio is at least 0.5s long
                                    if (pcmData.size >= sampleRate * 0.5 * 2) {
                                        val wavData = addWavHeader(pcmData, sampleRate)
                                        handler.post {
                                            triggerHapticFeedback()
                                            sendAudioToBackend(wavData)
                                        }
                                    } else {
                                        handler.post {
                                            updateState(STATE_LISTENING, "Listening silently...")
                                        }
                                    }
                                }
                            }
                        }

                        if (isSpeaking) {
                            val byteBuf = ByteArray(read * 2)
                            ByteBuffer.wrap(byteBuf).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(buffer, 0, read)
                            speechBuffer.write(byteBuf)
                        }
                    }
                }
            }.apply {
                priority = Thread.MAX_PRIORITY
                start()
            }
        } catch (e: Exception) {
            Log.e(TAG, "VAD error", e)
            updateState(STATE_ERROR, "Mic error: ${e.message}")
        }
    }

    private fun stopVadListening() {
        isRecording = false
        vadThread?.interrupt()
        vadThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    private fun addWavHeader(pcm: ByteArray, rate: Int): ByteArray {
        val totalDataLen = pcm.size + 36
        val byteRate = rate * 2 * 1
        val header = ByteArray(44)
        header[0] = 'R'.code.toByte(); header[1] = 'I'.code.toByte(); header[2] = 'F'.code.toByte(); header[3] = 'F'.code.toByte()
        header[4] = (totalDataLen and 0xff).toByte()
        header[5] = ((totalDataLen shr 8) and 0xff).toByte()
        header[6] = ((totalDataLen shr 16) and 0xff).toByte()
        header[7] = ((totalDataLen shr 24) and 0xff).toByte()
        header[8] = 'W'.code.toByte(); header[9] = 'A'.code.toByte(); header[10] = 'V'.code.toByte(); header[11] = 'E'.code.toByte()
        header[12] = 'f'.code.toByte(); header[13] = 'm'.code.toByte(); header[14] = 't'.code.toByte(); header[15] = ' '.code.toByte()
        header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0
        header[20] = 1; header[21] = 0 // PCM format
        header[22] = 1; header[23] = 0 // Mono
        header[24] = (rate and 0xff).toByte()
        header[25] = ((rate shr 8) and 0xff).toByte()
        header[26] = ((rate shr 16) and 0xff).toByte()
        header[27] = ((rate shr 24) and 0xff).toByte()
        header[28] = (byteRate and 0xff).toByte()
        header[29] = ((byteRate shr 8) and 0xff).toByte()
        header[30] = ((byteRate shr 16) and 0xff).toByte()
        header[31] = ((byteRate shr 24) and 0xff).toByte()
        header[32] = 2; header[33] = 0
        header[34] = 16; header[35] = 0
        header[36] = 'd'.code.toByte(); header[37] = 'a'.code.toByte(); header[38] = 't'.code.toByte(); header[39] = 'a'.code.toByte()
        header[40] = (pcm.size and 0xff).toByte()
        header[41] = ((pcm.size shr 8) and 0xff).toByte()
        header[42] = ((pcm.size shr 16) and 0xff).toByte()
        header[43] = ((pcm.size shr 24) and 0xff).toByte()

        val out = ByteArray(44 + pcm.size)
        System.arraycopy(header, 0, out, 0, 44)
        System.arraycopy(pcm, 0, out, 44, pcm.size)
        return out
    }

    // =========================================================================
    // Backend Communication
    // =========================================================================

    private fun sendAudioToBackend(wavBytes: ByteArray) {
        updateState(STATE_PROCESSING, "Transcribing voice signal...")
        val b64 = Base64.encodeToString(wavBytes, Base64.NO_WRAP)

        val jsonBody = JSONObject().apply {
            put("audio_b64", b64)
            put("mime_type", "audio/wav")
        }.toString()

        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())
        val request = Request.Builder()
            .url(TRANSCRIBE_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                handler.post {
                    broadcastLog("❌ Transcribe failed: ${e.message}")
                    updateState(STATE_ERROR, "Uplink offline")
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()

                handler.post {
                    try {
                        val json = JSONObject(body)
                        val ok = json.optBoolean("ok", false)
                        val text = json.optString("text", "")

                        if (ok && text.isNotEmpty()) {
                            broadcastLog("🗣️ You: \"$text\"")
                            updateState(STATE_PROCESSING, "Reasoning: \"$text\"")
                        } else {
                            updateState(STATE_LISTENING, "Listening silently...")
                        }
                    } catch (_: Exception) {
                        updateState(STATE_LISTENING, "Listening silently...")
                    }
                }
            }
        })
    }

    // =========================================================================
    // SSE Stream (Tracks Termux speaking state)
    // =========================================================================

    private fun connectSSEStream() {
        sseEventSource?.cancel()

        val request = Request.Builder()
            .url(STREAM_URL)
            .build()

        val factory = EventSources.createFactory(client)

        sseEventSource = factory.newEventSource(request, object : EventSourceListener() {

            override fun onOpen(eventSource: EventSource, response: Response) {
                Log.i(TAG, "SSE connected to backend")
            }

            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                try {
                    val json = JSONObject(data)
                    val eventType = json.optString("type", "")

                    if (eventType == "reply") {
                        val replyText = json.optString("text", "")
                        if (replyText.isNotEmpty()) {
                            handler.post {
                                broadcastLog("🤖 Termux: \"$replyText\"")
                            }
                        }
                    } else if (eventType == "snapshot") {
                        val phase = json.optString("phase", "")
                        if (phase == "speaking") {
                            isTermuxSpeaking = true
                            handler.post {
                                updateState(STATE_SPEAKING, "Termux speaking reply...")
                            }
                        } else if (isTermuxSpeaking && (phase == "standby" || phase == "idle")) {
                            isTermuxSpeaking = false
                            handler.post {
                                updateState(STATE_LISTENING, "Listening silently...")
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "SSE parse error", e)
                }
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                handler.postDelayed({ if (!isDestroyed) connectSSEStream() }, 5000)
            }

            override fun onClosed(eventSource: EventSource) {
                handler.postDelayed({ if (!isDestroyed) connectSSEStream() }, 3000)
            }
        })
    }
}
