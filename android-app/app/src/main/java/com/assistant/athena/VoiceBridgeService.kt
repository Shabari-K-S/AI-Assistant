package com.assistant.athena

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.app.NotificationCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import org.json.JSONObject
import java.io.IOException
import java.util.Locale
import java.util.concurrent.TimeUnit
import java.util.regex.Pattern

/**
 * A.T.H.E.N.A. — Adaptive Thinking Hands-free Engine for Neural Assistance
 *
 * High-Accuracy On-Device Acoustic Engine + Termux Neural AI Brain:
 *   - Uses Android's native high-precision acoustic speech recognizer (100% accurate on technical words like "telemetry log").
 *   - Wake word filtering (Athena, Atina, Adina, Athina, Atena).
 *   - Direct JSON dispatch to Termux HTTP /ask endpoint.
 *   - Single-voice audio output spoken exclusively by Termux Python TTS.
 */
class VoiceBridgeService : Service(), RecognitionListener {

    companion object {
        private const val TAG = "Athena.Service"
        private const val CHANNEL_ID = "athena_voice_bridge"
        private const val NOTIFICATION_ID = 7001

        // Backend endpoints — Termux evbridge.py
        private const val BACKEND_BASE = "http://127.0.0.1:2027"
        private const val ASK_URL = "$BACKEND_BASE/ask"
        private const val STREAM_URL = "$BACKEND_BASE/stream"

        // State constants
        const val STATE_STANDBY = "standby"
        const val STATE_LISTENING = "listening"
        const val STATE_PROCESSING = "processing"
        const val STATE_SPEAKING = "speaking"
        const val STATE_ERROR = "error"

        var onLogListener: ((String) -> Unit)? = null

        // Wake word phonetic pattern (Athena, Atina, Adina, Athina, etc.)
        private val WAKE_PATTERN = Pattern.compile(
            "\\b(?:hey\\s+|hi\\s+|ok\\s+|okay\\s+|hello\\s+)?(a[td]h?e?i?n[ae]|ath?ee?n[ae]|atena|atina|adina|adena|edina|ethina)\\b",
            Pattern.CASE_INSENSITIVE
        )
    }

    // --- Core components ---
    private var wakeLock: PowerManager.WakeLock? = null
    private val handler = Handler(Looper.getMainLooper())

    // --- Native High-Precision Speech Recognizer ---
    private var speechRecognizer: SpeechRecognizer? = null
    private var speechIntent: Intent? = null
    private var isListening = false
    private var isTermuxSpeaking = false
    private var isDestroyed = false

    // Follow-up conversation window state
    private var isAwaitingCommand = false
    private var followUpTimeoutRunnable: Runnable? = null

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
        Log.i(TAG, "═══ A.T.H.E.N.A. High-Accuracy Speech Engine starting ═══")

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "Athena::VoiceBridgeWakeLock"
        ).apply {
            acquire(24 * 60 * 60 * 1000L)
        }

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification(STATE_STANDBY, "Listening for 'Athena'..."))

        initSpeechRecognizer()
        connectSSEStream()

        broadcastLog("🎙️ ATHENA High-Accuracy Voice Engine active")
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge online ═══")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge shutting down ═══")
        isDestroyed = true

        followUpTimeoutRunnable?.let { handler.removeCallbacks(it) }
        destroySpeechRecognizer()

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
            STATE_LISTENING -> "🎙️ ATHENA — Listening..."
            STATE_PROCESSING -> "⚡ ATHENA — Processing..."
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
    // Speech Recognition Setup
    // =========================================================================

    private fun initSpeechRecognizer() {
        if (speechRecognizer != null) return

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "SpeechRecognizer not available on device")
            updateState(STATE_ERROR, "Speech recognition unavailable")
            return
        }

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
            setRecognitionListener(this@VoiceBridgeService)
        }

        speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 3000L)
        }

        startListeningSafe()
    }

    private fun destroySpeechRecognizer() {
        try {
            speechRecognizer?.stopListening()
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
        } catch (_: Exception) {}
        speechRecognizer = null
        isListening = false
    }

    private fun startListeningSafe() {
        if (isDestroyed || isTermuxSpeaking || isListening) return
        handler.post {
            try {
                if (speechRecognizer == null) {
                    speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
                        setRecognitionListener(this@VoiceBridgeService)
                    }
                }
                speechIntent?.let {
                    speechRecognizer?.startListening(it)
                    isListening = true
                    val stateLabel = if (isAwaitingCommand) "Awaiting command..." else "Listening for 'Athena'..."
                    updateState(STATE_LISTENING, stateLabel)
                }
            } catch (e: Exception) {
                Log.e(TAG, "startListening error", e)
                isListening = false
                restartListeningWithDelay(2000)
            }
        }
    }

    private fun restartListeningWithDelay(delayMs: Long = 800) {
        if (isDestroyed) return
        handler.postDelayed({
            if (!isDestroyed && !isTermuxSpeaking) {
                startListeningSafe()
            }
        }, delayMs)
    }

    // =========================================================================
    // RecognitionListener Callbacks
    // =========================================================================

    override fun onReadyForSpeech(params: Bundle?) {
        isListening = true
    }

    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {
        isListening = false
    }

    override fun onError(error: Int) {
        isListening = false
        val delay = when (error) {
            SpeechRecognizer.ERROR_NO_MATCH,
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> 500L
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> 1500L
            else -> 1000L
        }
        restartListeningWithDelay(delay)
    }

    override fun onResults(results: Bundle?) {
        isListening = false
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        if (matches.isNullOrEmpty()) {
            restartListeningWithDelay(400)
            return
        }

        val rawText = matches[0].trim()
        Log.i(TAG, "Heard: '$rawText'")

        // 1. If in 12-second follow-up window: accept ANY command directly
        if (isAwaitingCommand) {
            followUpTimeoutRunnable?.let { handler.removeCallbacks(it) }
            isAwaitingCommand = false
            triggerHapticFeedback()
            broadcastLog("🗣️ Command: \"$rawText\"")
            sendTextToBackend(rawText)
            return
        }

        // 2. Check for wake word
        val matcher = WAKE_PATTERN.matcher(rawText)
        if (matcher.find()) {
            triggerHapticFeedback()
            val command = rawText.substring(matcher.end()).trim().trim(',', '.', '!', '?')

            if (command.isEmpty()) {
                // User only said "Athena" -> Open 12-second follow-up window
                isAwaitingCommand = true
                broadcastLog("✨ Athena awake! (Say your command...)")
                updateState(STATE_LISTENING, "Listening for command...")

                followUpTimeoutRunnable?.let { handler.removeCallbacks(it) }
                followUpTimeoutRunnable = Runnable {
                    isAwaitingCommand = false
                    broadcastLog("⏱️ Listening window closed.")
                    updateState(STATE_STANDBY, "Listening for 'Athena'...")
                }
                handler.postDelayed(followUpTimeoutRunnable!!, 12000L)
                restartListeningWithDelay(300)
            } else {
                // Full sentence: "Athena, show telemetry log"
                broadcastLog("🎯 Wake hit: \"$command\"")
                sendTextToBackend(command)
            }
        } else {
            // Background speech without wake word -> discard silently
            broadcastLog("👂 Ignored: \"$rawText\"")
            restartListeningWithDelay(400)
        }
    }

    override fun onPartialResults(partialResults: Bundle?) {}
    override fun onEvent(eventType: Int, params: Bundle?) {}

    // =========================================================================
    // Backend Communication
    // =========================================================================

    private fun sendTextToBackend(prompt: String) {
        updateState(STATE_PROCESSING, "Processing: \"$prompt\"")

        val jsonBody = JSONObject().apply {
            put("text", prompt)
        }.toString()

        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())
        val request = Request.Builder()
            .url(ASK_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                handler.post {
                    broadcastLog("❌ Uplink failed: ${e.message}")
                    updateState(STATE_ERROR, "Backend offline")
                    restartListeningWithDelay(3000)
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()

                handler.post {
                    try {
                        val json = JSONObject(body)
                        val reply = json.optString("reply", "")
                        if (reply.isNotEmpty()) {
                            broadcastLog("🤖 Termux: \"$reply\"")
                        }
                    } catch (_: Exception) {}
                    // Listening will be resumed when Termux finishes speaking (tracked via SSE)
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
                                try { speechRecognizer?.stopListening() } catch (_: Exception) {}
                                isListening = false
                                updateState(STATE_SPEAKING, "Termux speaking reply...")
                            }
                        } else if (isTermuxSpeaking && (phase == "standby" || phase == "idle")) {
                            isTermuxSpeaking = false
                            handler.post {
                                updateState(STATE_STANDBY, "Listening for 'Athena'...")
                                startListeningSafe()
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
