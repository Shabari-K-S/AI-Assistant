package com.assistant.athena

import android.annotation.SuppressLint
import android.app.*
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
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
 * 100% Silent Direct Hardware Audio Engine (ZERO Beeps, ZERO Boops, ZERO Chimes):
 *   - Direct PCM stream via AudioRecord with Hardware AGC & Noise Suppressor.
 *   - Completely eliminates Google SpeechRecognizer and all system sound cues.
 *   - Transcribes via Termux /transcribe endpoint (Gemini 2.5 Flash / Groq Whisper).
 *   - All voice replies spoken exclusively by Termux Python TTS engine.
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

    // --- Hardware AudioRecord Engine ---
    private var audioRecord: AudioRecord? = null
    private var vadThread: Thread? = null
    private var isRecording = false
    private var isTermuxSpeaking = false
    private var isDestroyed = false

    // Hardware Audio Effects (Clean & Boost Mobile Mic)
    private var agc: AutomaticGainControl? = null
    private var ns: NoiseSuppressor? = null
    private var aec: AcousticEchoCanceler? = null

    // Audio config (16 kHz, 16-bit Mono PCM)
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
        Log.i(TAG, "═══ A.T.H.E.N.A. 100% Silent Audio Engine starting ═══")

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "Athena::VoiceBridgeWakeLock"
        ).apply {
            acquire(24 * 60 * 60 * 1000L)
        }

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification(STATE_STANDBY, "Silent standby active (0 beeps)..."))

        connectSSEStream()
        startSilentHardwareCapture()

        broadcastLog("🛡️ ATHENA Silent Engine active (Zero Beeps/Boops)")
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge online ═══")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge shutting down ═══")
        isDestroyed = true

        stopSilentHardwareCapture()

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
            STATE_LISTENING -> "🎙️ ATHENA — Hearing Voice (Silent)"
            STATE_PROCESSING -> "⚡ ATHENA — Thinking..."
            STATE_SPEAKING -> "🔊 ATHENA — Speaking (Termux)..."
            STATE_ERROR -> "⚠️ ATHENA — Error"
            else -> "🛡️ ATHENA — Standby (Say 'Athena')"
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
    // 100% Silent Direct Hardware Audio Capture (Zero Beeps/Boops)
    // =========================================================================

    @SuppressLint("MissingPermission")
    private fun startSilentHardwareCapture() {
        if (isRecording || isDestroyed) return

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                channelConfig,
                audioFormat,
                minBufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                // Fallback to standard MIC
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    sampleRate,
                    channelConfig,
                    audioFormat,
                    minBufferSize
                )
            }

            val sessionId = audioRecord?.audioSessionId ?: 0
            if (sessionId != 0) {
                try {
                    if (AutomaticGainControl.isAvailable()) {
                        agc = AutomaticGainControl.create(sessionId)?.apply { enabled = true }
                    }
                    if (NoiseSuppressor.isAvailable()) {
                        ns = NoiseSuppressor.create(sessionId)?.apply { enabled = true }
                    }
                    if (AcousticEchoCanceler.isAvailable()) {
                        aec = AcousticEchoCanceler.create(sessionId)?.apply { enabled = true }
                    }
                } catch (_: Exception) {}
            }

            audioRecord?.startRecording()
            isRecording = true

            vadThread = Thread {
                val buffer = ShortArray(1024)
                val speechBuffer = ByteArrayOutputStream()
                var isSpeaking = false
                var silenceFrames = 0
                var speechFrames = 0
                var noiseFloor = 350.0

                while (isRecording && !isDestroyed) {
                    if (isTermuxSpeaking) {
                        Thread.sleep(120)
                        continue
                    }

                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0) {
                        var sum = 0.0
                        for (i in 0 until read) {
                            sum += abs(buffer[i].toDouble())
                        }
                        val rms = sum / read

                        // Dynamic background noise floor tracking
                        if (!isSpeaking) {
                            noiseFloor = noiseFloor * 0.97 + rms * 0.03
                        }

                        val speechThreshold = maxOf(noiseFloor * 1.8, 550.0)

                        if (rms > speechThreshold) {
                            silenceFrames = 0
                            speechFrames++
                            if (!isSpeaking && speechFrames >= 2) {
                                isSpeaking = true
                                speechBuffer.reset()
                                handler.post {
                                    updateState(STATE_LISTENING, "Hearing voice...")
                                }
                            }
                        } else {
                            if (isSpeaking) {
                                silenceFrames++
                                // ~0.75s of silence after speech -> audio turn complete
                                if (silenceFrames >= 11) {
                                    isSpeaking = false
                                    speechFrames = 0
                                    val pcmData = speechBuffer.toByteArray()
                                    speechBuffer.reset()

                                    // Send if at least 0.45s long
                                    if (pcmData.size >= sampleRate * 0.45 * 2) {
                                        val wavData = addWavHeader(pcmData, sampleRate)
                                        handler.post {
                                            sendAudioToBackend(wavData)
                                        }
                                    } else {
                                        handler.post {
                                            updateState(STATE_STANDBY, "Listening for 'Athena'...")
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
            Log.e(TAG, "Hardware audio capture error", e)
            updateState(STATE_ERROR, "Mic error: ${e.message}")
        }
    }

    private fun stopSilentHardwareCapture() {
        isRecording = false
        vadThread?.interrupt()
        vadThread = null
        try {
            agc?.release()
            ns?.release()
            aec?.release()
        } catch (_: Exception) {}
        agc = null
        ns = null
        aec = null
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
                    broadcastLog("❌ Uplink offline: ${e.message}")
                    updateState(STATE_STANDBY, "Listening for 'Athena'...")
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
                        val reason = json.optString("reason", "")
                        val command = json.optString("command", "")

                        if (ok && text.isNotEmpty()) {
                            triggerHapticFeedback()
                            if (command.isNotEmpty()) {
                                broadcastLog("🎯 Wake hit: \"$command\"")
                                updateState(STATE_PROCESSING, "Processing: \"$command\"")
                            } else {
                                broadcastLog("✨ Athena awake! (\"$text\")")
                                updateState(STATE_PROCESSING, "Athena listening...")
                            }
                        } else if (reason == "no_wake_word") {
                            broadcastLog("👂 Ignored (No wake word): \"$text\"")
                            updateState(STATE_STANDBY, "Listening for 'Athena'...")
                        } else {
                            updateState(STATE_STANDBY, "Listening for 'Athena'...")
                        }
                    } catch (_: Exception) {
                        updateState(STATE_STANDBY, "Listening for 'Athena'...")
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
                                updateState(STATE_STANDBY, "Listening for 'Athena'...")
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
