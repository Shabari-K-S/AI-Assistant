package com.assistant.athena

import android.app.*
import android.content.Context
import android.content.Intent
import android.media.AudioManager
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
import java.util.*
import java.util.concurrent.TimeUnit

/**
 * A.T.H.E.N.A. — Adaptive Thinking Hands-free Engine for Neural Assistance
 *
 * 24/7 Foreground Voice Bridge:
 *   - Continuous SpeechRecognizer listening for "Athena" / phonetic variants.
 *   - Uplinks prompts to Termux backend (/ask).
 *   - TTS audio output is handled EXCLUSIVELY by the Termux Python engine
 *     (no duplicate Android speech).
 */
class VoiceBridgeService : Service() {

    companion object {
        private const val TAG = "Athena.Service"
        private const val CHANNEL_ID = "athena_voice_bridge"
        private const val NOTIFICATION_ID = 7001

        // Backend endpoints — Termux evbridge.py
        private const val BACKEND_BASE = "http://127.0.0.1:2027"
        private const val ASK_URL = "$BACKEND_BASE/ask"
        private const val STREAM_URL = "$BACKEND_BASE/stream"

        // Wake word variants (covering all regional phonetic variations)
        private val WAKE_WORDS = listOf(
            "athena", "hey athena", "athena,", "hey athena,",
            "a]thena", "athena.", "athina", "a tina", "a thena",
            "athene", "athana", "athenna", "atena", "attina",
            "atina", "hey atina", "hi atina", "ok atina", "okay atina", "atina,",
            "adina", "hey adina", "hi adina", "ok adina", "okay adina", "adina,",
            "atheena", "hey atheena", "hi atheena",
            "adena", "adhena", "ethina", "edina",
            "sara", "hey sara", "sarah", "zara", "alexa", "assistant"
        )

        // Phonetic Regex Matcher for any variation of A-t-h-e-n-a / A-t-i-n-a / A-d-i-n-a
        private val WAKE_REGEX = Regex(
            "(?i)\\b(?:hey\\s+|hi\\s+|ok\\s+|okay\\s+|hello\\s+)?(a[td]h?e?i?n[ae]|ath?ee?n[ae]|atena|atina|adina|adena|edina|ethina)\\b"
        )

        // Restart delays
        private const val RESTART_DELAY_NORMAL_MS = 250L
        private const val RESTART_DELAY_ERROR_MS = 800L
        private const val RESTART_DELAY_AFTER_RESPONSE_MS = 1000L

        // State constants for notification
        const val STATE_STANDBY = "standby"
        const val STATE_LISTENING = "listening"
        const val STATE_PROCESSING = "processing"
        const val STATE_SPEAKING = "speaking"
        const val STATE_ERROR = "error"

        var onLogListener: ((String) -> Unit)? = null
    }

    // --- Core components ---
    private var speechRecognizer: SpeechRecognizer? = null
    private var speechIntent: Intent? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private val handler = Handler(Looper.getMainLooper())
    private val audioManager by lazy { getSystemService(Context.AUDIO_SERVICE) as AudioManager }

    // --- Network ---
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()
    private var sseEventSource: EventSource? = null

    // --- State ---
    private var isDestroyed = false
    private var isListening = false
    private var isTermuxSpeaking = false
    private var currentState = STATE_STANDBY
    private var consecutiveErrors = 0

    // Two-stage conversation state ("Hey Google" style)
    private var isAwaitingCommand = false
    private var awaitingCommandTimeout = 0L

    // =========================================================================
    // Beep & Chime Suppression Engine (Non-Intrusive)
    // =========================================================================

    private fun suppressMicrophoneBeep() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                audioManager.adjustStreamVolume(AudioManager.STREAM_SYSTEM, AudioManager.ADJUST_MUTE, 0)
            }
            handler.postDelayed({
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        audioManager.adjustStreamVolume(AudioManager.STREAM_SYSTEM, AudioManager.ADJUST_UNMUTE, 0)
                    }
                } catch (_: Exception) {}
            }, 80L)
        } catch (e: Exception) {
            Log.w(TAG, "Beep mute error: ${e.message}")
        }
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
                v?.vibrate(50L)
            }
        } catch (_: Exception) {}
    }

    private fun broadcastLog(msg: String) {
        try {
            onLogListener?.invoke(msg)
        } catch (_: Exception) {}
    }

    // =========================================================================
    // Service Lifecycle
    // =========================================================================

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge starting (Termux Audio Mode) ═══")

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "Athena::VoiceBridgeWakeLock"
        ).apply {
            acquire(24 * 60 * 60 * 1000L)
        }

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification(STATE_STANDBY, "Listening for \"Athena\"..."))

        connectSSEStream()
        initSpeechRecognizer()

        broadcastLog("🎙️ Voice Bridge initialized (Audio: Python Termux TTS)")
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge online ═══")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge shutting down ═══")
        isDestroyed = true

        handler.removeCallbacksAndMessages(null)
        speechRecognizer?.destroy()
        speechRecognizer = null

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
                description = "24/7 always-on voice bridge for AI assistant"
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
            else -> "🛡️ ATHENA — Standing By (Silent)"
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
        currentState = state
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(state, detail))
    }

    // =========================================================================
    // Continuous SpeechRecognizer
    // =========================================================================

    private fun initSpeechRecognizer() {
        if (isDestroyed) return

        speechRecognizer?.destroy()

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.e(TAG, "SpeechRecognizer not available on this device!")
            updateState(STATE_ERROR, "Speech recognition not available")
            return
        }

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)

        speechIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, packageName)
            putExtra("android.speech.extra.DICTATION_MODE", true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 5000L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
        }

        speechRecognizer?.setRecognitionListener(object : RecognitionListener {

            override fun onReadyForSpeech(params: Bundle?) {
                isListening = true
                consecutiveErrors = 0
                if (isAwaitingCommand) {
                    updateState(STATE_LISTENING, "Listening for your command...")
                } else {
                    updateState(STATE_LISTENING, "Listening for \"Athena\"...")
                }
            }

            override fun onBeginningOfSpeech() {
                Log.d(TAG, "Speech detected")
            }

            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}

            override fun onEndOfSpeech() {
                isListening = false
            }

            override fun onError(error: Int) {
                isListening = false
                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                        consecutiveErrors = 0
                        restartListening(RESTART_DELAY_NORMAL_MS)
                    }
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> {
                        restartListening(RESTART_DELAY_ERROR_MS)
                    }
                    SpeechRecognizer.ERROR_AUDIO -> {
                        consecutiveErrors++
                        if (consecutiveErrors > 5) {
                            consecutiveErrors = 0
                            handler.postDelayed({ initSpeechRecognizer() }, 2000)
                        } else {
                            restartListening(RESTART_DELAY_ERROR_MS)
                        }
                    }
                    else -> {
                        consecutiveErrors++
                        val delay = minOf(
                            RESTART_DELAY_ERROR_MS * (1L shl minOf(consecutiveErrors, 4)),
                            15_000L
                        )
                        restartListening(delay)
                    }
                }
            }

            override fun onResults(results: Bundle?) {
                isListening = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)

                if (!matches.isNullOrEmpty()) {
                    val transcript = matches[0]
                    Log.i(TAG, "Transcribed: \"$transcript\"")
                    processTranscript(transcript)
                } else {
                    restartListening(RESTART_DELAY_NORMAL_MS)
                }
            }

            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        startListening()
    }

    private fun startListening() {
        if (isDestroyed || isTermuxSpeaking) return
        try {
            suppressMicrophoneBeep()
            speechRecognizer?.startListening(speechIntent)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start listening", e)
            restartListening(RESTART_DELAY_ERROR_MS)
        }
    }

    private fun restartListening(delayMs: Long) {
        if (isDestroyed) return
        handler.postDelayed({
            if (!isDestroyed && !isTermuxSpeaking) {
                startListening()
            }
        }, delayMs)
    }

    // =========================================================================
    // Wake Word Detection & Two-Stage Command Handling
    // =========================================================================

    private fun processTranscript(transcript: String) {
        val lower = transcript.lowercase(Locale.ROOT).trim()

        // 1. If we are in the follow-up window after "Athena", take this speech directly as command!
        if (isAwaitingCommand && System.currentTimeMillis() < awaitingCommandTimeout) {
            isAwaitingCommand = false
            broadcastLog("🎯 Command: \"$transcript\"")
            updateState(STATE_PROCESSING, "Processing: \"$transcript\"")
            sendToBackend(transcript)
            return
        }
        isAwaitingCommand = false

        // 2. Check for Wake Word
        var query: String? = null

        // A. Direct list check
        for (wake in WAKE_WORDS) {
            if (lower.startsWith(wake)) {
                query = transcript.substring(wake.length).trim()
                query = query.trimStart(',', '.', '!', '?', ' ')
                break
            }
            val idx = lower.indexOf(wake)
            if (idx >= 0) {
                query = transcript.substring(idx + wake.length).trim()
                query = query.trimStart(',', '.', '!', '?', ' ')
                break
            }
        }

        // B. Regex phonetic check (e.g. "Atina", "Adina", "Atena", etc.)
        if (query == null) {
            val match = WAKE_REGEX.find(lower)
            if (match != null) {
                val endIdx = match.range.last + 1
                query = if (endIdx < transcript.length) {
                    transcript.substring(endIdx).trim().trimStart(',', '.', '!', '?', ' ')
                } else {
                    ""
                }
            }
        }

        if (query == null) {
            // Discard speech that doesn't include the wake word
            broadcastLog("👂 Heard (No wake word): \"$transcript\"")
            restartListening(RESTART_DELAY_NORMAL_MS)
            return
        }

        if (query.isEmpty()) {
            // Wake word only -> Trigger gentle haptic vibration and listen for command!
            triggerHapticFeedback()
            broadcastLog("✨ Athena awake! Listening for your command...")
            updateState(STATE_LISTENING, "Yes? Listening for your command...")
            isAwaitingCommand = true
            awaitingCommandTimeout = System.currentTimeMillis() + 12_000L // 12 seconds window
            restartListening(RESTART_DELAY_NORMAL_MS)
            return
        }

        // One-shot: "Athena, what time is it?"
        broadcastLog("🎯 Wake triggered! Query: \"$query\"")
        updateState(STATE_PROCESSING, "Processing: \"$query\"")
        sendToBackend(query)
    }

    // =========================================================================
    // Backend Communication (Direct Synchronous /ask)
    // =========================================================================

    private fun sendToBackend(query: String) {
        val jsonBody = JSONObject().put("text", query).toString()
        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(ASK_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "Failed to reach Termux /ask: ${e.message}")
                handler.post {
                    broadcastLog("❌ Backend error: ${e.message} (Is Termux running?)")
                    updateState(STATE_ERROR, "Termux offline: ${e.message}")
                    restartListening(RESTART_DELAY_ERROR_MS)
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()

                handler.post {
                    try {
                        val json = JSONObject(body)
                        val ok = json.optBoolean("ok", false)
                        val reply = json.optString("reply", "")

                        if (ok && reply.isNotEmpty()) {
                            // Termux Python TTS speaks the reply directly through phone speaker!
                            broadcastLog("🤖 Termux Speaking: \"$reply\"")
                            updateState(STATE_SPEAKING, "Termux speaking reply...")
                            // Resume listening smoothly after Termux audio finishes
                            restartListening(RESTART_DELAY_AFTER_RESPONSE_MS)
                        } else {
                            broadcastLog("⚠️ Sent: '$query' (Waiting for reply...)")
                            updateState(STATE_PROCESSING, "Thinking...")
                            restartListening(RESTART_DELAY_NORMAL_MS)
                        }
                    } catch (e: Exception) {
                        broadcastLog("⚠️ Parse error: ${e.message}")
                        restartListening(RESTART_DELAY_NORMAL_MS)
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

                    if (eventType == "snapshot") {
                        val phase = json.optString("phase", "")
                        if (phase == "speaking") {
                            isTermuxSpeaking = true
                            handler.post {
                                updateState(STATE_SPEAKING, "Termux speaking...")
                                try { speechRecognizer?.stopListening() } catch (_: Exception) {}
                            }
                        } else if (isTermuxSpeaking && (phase == "standby" || phase == "idle")) {
                            isTermuxSpeaking = false
                            handler.post {
                                updateState(STATE_STANDBY, "Listening for \"Athena\"...")
                                restartListening(RESTART_DELAY_NORMAL_MS)
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
