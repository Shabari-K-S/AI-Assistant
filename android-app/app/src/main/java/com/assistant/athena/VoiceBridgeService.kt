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
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
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
 * 24/7 Foreground Service that continuously listens for the "Athena" wake word
 * using Android's native SpeechRecognizer with AUTOMATIC BEEP SUPPRESSION.
 *
 * Beep Elimination:
 *   - Automatically mutes notification/system streams before startListening()
 *   - Restores volume during TTS speech playback so audio replies are loud and clear
 *   - Zero microphone on/off chime noise!
 */
class VoiceBridgeService : Service(), TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "Athena.Service"
        private const val CHANNEL_ID = "athena_voice_bridge"
        private const val NOTIFICATION_ID = 7001

        // Backend endpoints — Termux evbridge.py
        private const val BACKEND_BASE = "http://127.0.0.1:2027"
        private const val PROMPT_URL = "$BACKEND_BASE/prompt"
        private const val STREAM_URL = "$BACKEND_BASE/stream"
        private const val STATE_URL = "$BACKEND_BASE/state"

        // Wake word variants (case-insensitive matching)
        private val WAKE_WORDS = listOf(
            "athena", "hey athena", "athena,", "hey athena,",
            "a]thena", "athena.", "athina", "a tina", "a thena",
            // Common STT mishearings
            "athene", "athana", "athenna", "atena",
        )

        // Restart delays (smooth, silent loop)
        private const val RESTART_DELAY_NORMAL_MS = 250L
        private const val RESTART_DELAY_ERROR_MS = 800L
        private const val RESTART_DELAY_AFTER_RESPONSE_MS = 700L

        // State constants for notification
        const val STATE_STANDBY = "standby"
        const val STATE_LISTENING = "listening"
        const val STATE_PROCESSING = "processing"
        const val STATE_SPEAKING = "speaking"
        const val STATE_ERROR = "error"
    }

    // --- Core components ---
    private var speechRecognizer: SpeechRecognizer? = null
    private var speechIntent: Intent? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var wakeLock: PowerManager.WakeLock? = null
    private val handler = Handler(Looper.getMainLooper())
    private val audioManager by lazy { getSystemService(Context.AUDIO_SERVICE) as AudioManager }

    // --- Network ---
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()
    private var sseEventSource: EventSource? = null

    // --- State ---
    private var isDestroyed = false
    private var isListening = false
    private var isSpeaking = false
    private var currentState = STATE_STANDBY
    private var consecutiveErrors = 0
    private var pendingReply = false
    private var isMuted = false

    // =========================================================================
    // Beep & Chime Suppression Engine
    // =========================================================================

    /**
     * Suppress the Android OS microphone start/stop beep by temporarily
     * muting the notification, system, and music streams during startListening().
     */
    private fun suppressMicrophoneBeep() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                audioManager.adjustStreamVolume(AudioManager.STREAM_NOTIFICATION, AudioManager.ADJUST_MUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_SYSTEM, AudioManager.ADJUST_MUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_ALARM, AudioManager.ADJUST_MUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, 0)
            } else {
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_NOTIFICATION, true)
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_SYSTEM, true)
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_MUSIC, true)
            }
            isMuted = true
        } catch (e: Exception) {
            Log.w(TAG, "Beep mute error: ${e.message}")
        }
    }

    /**
     * Restore audio streams when speaking responses so TTS is completely audible.
     */
    private fun restoreAudioStreams() {
        if (!isMuted) return
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                audioManager.adjustStreamVolume(AudioManager.STREAM_NOTIFICATION, AudioManager.ADJUST_UNMUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_SYSTEM, AudioManager.ADJUST_UNMUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_ALARM, AudioManager.ADJUST_UNMUTE, 0)
                audioManager.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, 0)
            } else {
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_NOTIFICATION, false)
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_SYSTEM, false)
                @Suppress("DEPRECATION")
                audioManager.setStreamMute(AudioManager.STREAM_MUSIC, false)
            }
            isMuted = false
        } catch (e: Exception) {
            Log.w(TAG, "Audio restore error: ${e.message}")
        }
    }

    // =========================================================================
    // Service Lifecycle
    // =========================================================================

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "═══ A.T.H.E.N.A. Silent Voice Bridge starting ═══")

        // 1. Acquire CPU wake lock — prevents deep sleep with screen off
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "Athena::VoiceBridgeWakeLock"
        ).apply {
            acquire(24 * 60 * 60 * 1000L) // 24 hours max
        }

        // 2. Create notification channel and start as foreground service
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification(STATE_STANDBY, "Initializing..."))

        // 3. Initialize Text-to-Speech for speaking responses
        tts = TextToSpeech(this, this)

        // 4. Connect SSE stream for receiving backend replies
        connectSSEStream()

        // 5. Initialize and start continuous speech recognition with beep suppression
        initSpeechRecognizer()

        Log.i(TAG, "═══ A.T.H.E.N.A. Silent Voice Bridge online ═══")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "═══ A.T.H.E.N.A. Voice Bridge shutting down ═══")
        isDestroyed = true

        restoreAudioStreams()

        handler.removeCallbacksAndMessages(null)
        speechRecognizer?.destroy()
        speechRecognizer = null

        sseEventSource?.cancel()
        sseEventSource = null

        tts?.stop()
        tts?.shutdown()
        tts = null

        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // =========================================================================
    // Notification (Ongoing — keeps the service alive)
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
            else -> android.R.drawable.ic_lock_silent_mode // standby
        }

        val title = when (state) {
            STATE_LISTENING -> "🎙️ ATHENA — Listening..."
            STATE_PROCESSING -> "⚡ ATHENA — Processing..."
            STATE_SPEAKING -> "🔊 ATHENA — Speaking..."
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
    // Continuous SpeechRecognizer with Zero Beeping
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
            // Extra flags to minimize OS sound prompts
            putExtra("android.speech.extra.DICTATION_MODE", true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 5000L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
        }

        speechRecognizer?.setRecognitionListener(object : RecognitionListener {

            override fun onReadyForSpeech(params: Bundle?) {
                isListening = true
                consecutiveErrors = 0
                updateState(STATE_LISTENING, "Listening for \"Athena\"...")
                Log.d(TAG, "Mic open (silent)")
            }

            override fun onBeginningOfSpeech() {
                Log.d(TAG, "Speech detected")
            }

            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}

            override fun onEndOfSpeech() {
                isListening = false
                Log.d(TAG, "Speech ended — evaluating wake phrase...")
            }

            override fun onError(error: Int) {
                isListening = false
                val errorMsg = speechErrorToString(error)
                Log.d(TAG, "Silent restart on: $errorMsg")

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
                    Log.i(TAG, "Transcript: \"$transcript\"")
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
        if (isDestroyed || isSpeaking) return
        try {
            // Mute before calling startListening so the system start-beep is completely silent
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
            if (!isDestroyed && !isSpeaking) {
                startListening()
            }
        }, delayMs)
    }

    // =========================================================================
    // Wake Word Detection & Query Extraction
    // =========================================================================

    private fun processTranscript(transcript: String) {
        val lower = transcript.lowercase(Locale.ROOT).trim()

        var query: String? = null

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

        if (query == null) {
            // No wake word detected — silently restart listening
            Log.d(TAG, "Discarded (no wake word): \"$transcript\"")
            restartListening(RESTART_DELAY_NORMAL_MS)
            return
        }

        if (query.isEmpty()) {
            Log.i(TAG, "Wake word only — listening for follow-up command...")
            updateState(STATE_LISTENING, "Yes? Listening for your command...")
            restartListening(RESTART_DELAY_NORMAL_MS)
            return
        }

        Log.i(TAG, "═══ Wake word triggered! Query: \"$query\" ═══")
        updateState(STATE_PROCESSING, "Processing: \"$query\"")
        sendToBackend(query)
    }

    // =========================================================================
    // Backend Communication
    // =========================================================================

    private fun sendToBackend(query: String) {
        pendingReply = true
        val jsonBody = JSONObject().put("text", query).toString()
        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(PROMPT_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "Failed to reach Termux backend: ${e.message}")
                handler.post {
                    updateState(STATE_ERROR, "Backend unreachable: ${e.message}")
                    pendingReply = false
                    restartListening(RESTART_DELAY_ERROR_MS)
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                Log.d(TAG, "Backend accepted prompt: $body")
                response.close()

                handler.post {
                    updateState(STATE_PROCESSING, "Thinking...")
                    handler.postDelayed({
                        if (pendingReply) {
                            Log.w(TAG, "No SSE reply within 30s — resuming listening")
                            pendingReply = false
                            restartListening(RESTART_DELAY_NORMAL_MS)
                        }
                    }, 30_000)
                }
            }
        })
    }

    // =========================================================================
    // SSE Stream — Receives replies from the Termux backend
    // =========================================================================

    private fun connectSSEStream() {
        sseEventSource?.cancel()

        val request = Request.Builder()
            .url(STREAM_URL)
            .build()

        val factory = EventSources.createFactory(client)

        sseEventSource = factory.newEventSource(request, object : EventSourceListener() {

            override fun onOpen(eventSource: EventSource, response: Response) {
                Log.i(TAG, "SSE stream connected to backend")
            }

            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                try {
                    val json = JSONObject(data)
                    val eventType = json.optString("type", "")

                    when (eventType) {
                        "reply" -> {
                            val replyText = json.optString("text", "")
                            if (replyText.isNotEmpty() && pendingReply) {
                                pendingReply = false
                                Log.i(TAG, "═══ Reply received: \"${replyText.take(80)}...\" ═══")
                                handler.post { speakReply(replyText) }
                            }
                        }
                        "snapshot" -> {
                            val phase = json.optString("phase", "standby")
                            val reply = json.optString("reply", "")
                            if (reply.isNotEmpty() && pendingReply && phase == "speaking") {
                                pendingReply = false
                                handler.post { speakReply(reply) }
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "SSE parse error", e)
                }
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                Log.w(TAG, "SSE stream disconnected: ${t?.message} — reconnecting in 5s")
                handler.postDelayed({
                    if (!isDestroyed) connectSSEStream()
                }, 5000)
            }

            override fun onClosed(eventSource: EventSource) {
                Log.w(TAG, "SSE stream closed — reconnecting in 3s")
                handler.postDelayed({
                    if (!isDestroyed) connectSSEStream()
                }, 3000)
            }
        })
    }

    // =========================================================================
    // Text-to-Speech — Speak the assistant's reply (Full Volume)
    // =========================================================================

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
            tts?.setSpeechRate(1.05f)
            ttsReady = true
            Log.i(TAG, "TTS engine ready")

            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    isSpeaking = true
                    // Restore audio so the voice reply is loud and clear
                    restoreAudioStreams()
                    handler.post { updateState(STATE_SPEAKING, "Speaking response...") }
                }

                override fun onDone(utteranceId: String?) {
                    isSpeaking = false
                    Log.d(TAG, "TTS finished — resuming silent listening")
                    handler.post {
                        updateState(STATE_STANDBY, "Listening for \"Athena\"...")
                        restartListening(RESTART_DELAY_AFTER_RESPONSE_MS)
                    }
                }

                @Deprecated("Deprecated in API level 21")
                override fun onError(utteranceId: String?) {
                    isSpeaking = false
                    handler.post {
                        restartListening(RESTART_DELAY_NORMAL_MS)
                    }
                }
            })
        } else {
            Log.e(TAG, "TTS initialization failed with status: $status")
            ttsReady = false
        }
    }

    private fun speakReply(text: String) {
        if (!ttsReady || text.isBlank()) {
            restartListening(RESTART_DELAY_NORMAL_MS)
            return
        }

        updateState(STATE_SPEAKING, "Speaking: \"${text.take(50)}...\"")

        try { speechRecognizer?.stopListening() } catch (_: Exception) {}

        // Unmute before speaking so the user hears ATHENA's voice
        restoreAudioStreams()

        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "athena_reply_${System.currentTimeMillis()}")
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    private fun speechErrorToString(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_AUDIO -> "ERROR_AUDIO"
        SpeechRecognizer.ERROR_CLIENT -> "ERROR_CLIENT"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "ERROR_INSUFFICIENT_PERMISSIONS"
        SpeechRecognizer.ERROR_NETWORK -> "ERROR_NETWORK"
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "ERROR_NETWORK_TIMEOUT"
        SpeechRecognizer.ERROR_NO_MATCH -> "ERROR_NO_MATCH"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "ERROR_RECOGNIZER_BUSY"
        SpeechRecognizer.ERROR_SERVER -> "ERROR_SERVER"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "ERROR_SPEECH_TIMEOUT"
        else -> "UNKNOWN_ERROR($error)"
    }
}
