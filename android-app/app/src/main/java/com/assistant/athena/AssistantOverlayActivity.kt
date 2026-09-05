package com.assistant.athena

import android.Manifest
import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.text.Html
import android.text.Spanned
import android.util.Base64
import android.util.Log
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.widget.NestedScrollView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import com.assistant.athena.whisper.WhisperOfflineTranscriber
import com.assistant.athena.ui.AudioWaveformView
import com.assistant.athena.ui.OrbView
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
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.abs

/**
 * Perplexity-Style Floating HUD Assistant Overlay Activity.
 * Connected via Real-Time SSE Stream (GET /stream) and live prompt uplink (POST /prompt).
 * Supports streaming responses, live tool execution feedback, dynamic waveform, and 3D crystal orb.
 */
class AssistantOverlayActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "Athena.Overlay"
        private const val BACKEND_BASE = "http://127.0.0.1:2027"
        private const val STREAM_URL = "$BACKEND_BASE/stream"
        private const val PROMPT_URL = "$BACKEND_BASE/prompt"
        private const val TRANSCRIBE_URL = "$BACKEND_BASE/transcribe"
        private const val PERMISSION_REQUEST_RECORD = 201
    }

    // UI Elements
    private lateinit var rootOverlayLayout: View
    private lateinit var viewDismissBackdrop: View
    private lateinit var orbView: OrbView
    private lateinit var txtAssistantTitle: TextView
    private lateinit var waveformVisualizer: AudioWaveformView
    private lateinit var cardResponseContainer: NestedScrollView
    private lateinit var layoutUserPromptRow: LinearLayout
    private lateinit var txtUserPrompt: TextView
    private lateinit var txtStatusTelemetry: TextView
    private lateinit var viewPromptDivider: View
    private lateinit var txtResponseContent: TextView
    private lateinit var layoutResponseActions: LinearLayout
    private lateinit var btnCopyResponse: ImageButton
    private lateinit var btnSpeakResponse: ImageButton
    private lateinit var layoutTextInputRow: LinearLayout
    private lateinit var editQueryInput: EditText
    private lateinit var btnSendTextQuery: ImageButton
    private lateinit var btnToggleKeyboard: ImageButton
    private lateinit var btnVisionSearch: ImageButton
    private lateinit var btnMicAction: ImageButton

    // Screen Context Preview
    private lateinit var cardScreenContextPreview: LinearLayout
    private lateinit var imgScreenThumbnail: ImageView
    private lateinit var btnRemoveScreenContext: ImageButton
    private var isScreenContextAttached: Boolean = false

    // Suggestion Chips
    private lateinit var chipNotifications: TextView
    private lateinit var chipScreen: TextView
    private lateinit var chipNews: TextView
    private lateinit var chipSchedule: TextView
    private lateinit var chipSystem: TextView

    // Audio Capture State
    private var audioRecord: AudioRecord? = null
    private var recordThread: Thread? = null
    private var isRecording = false
    private val handler = Handler(Looper.getMainLooper())
    private val sampleRate = 16000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
    private val minBufferSize = maxOf(AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat), 4096)

    // Android TTS & Echo Guard
    private var tts: TextToSpeech? = null
    private var isTtsReady = false
    private var pendingSpeechText: String? = null
    @Volatile private var isTtsSpeaking = false
    @Volatile private var ttsQuietUntil = 0L

    // HTTP & SSE Clients
    private val client = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS) // Infinite read timeout for SSE stream
        .writeTimeout(8, TimeUnit.SECONDS)
        .build()
    private var sseEventSource: EventSource? = null
    private var lastSpokenText = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_assistant_overlay)

        bindViews()
        setupListeners()
        initTTS()
        connectSSEStream()
        triggerHaptic(VibrationEffect.EFFECT_CLICK)

        // Preload On-Device Whisper TFLite model in background
        CoroutineScope(Dispatchers.IO).launch {
            WhisperOfflineTranscriber.initialize(this@AssistantOverlayActivity)
        }

        // Check audio permissions & begin capture
        if (hasAudioPermission()) {
            startAudioRecording()
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.RECORD_AUDIO),
                PERMISSION_REQUEST_RECORD
            )
        }
    }

    private fun bindViews() {
        rootOverlayLayout = findViewById(R.id.rootOverlayLayout)
        viewDismissBackdrop = findViewById(R.id.viewDismissBackdrop)
        orbView = findViewById(R.id.orbView)
        txtAssistantTitle = findViewById(R.id.txtAssistantTitle)
        waveformVisualizer = findViewById(R.id.waveformVisualizer)
        cardResponseContainer = findViewById(R.id.cardResponseContainer)
        layoutUserPromptRow = findViewById(R.id.layoutUserPromptRow)
        txtUserPrompt = findViewById(R.id.txtUserPrompt)
        txtStatusTelemetry = findViewById(R.id.txtStatusTelemetry)
        viewPromptDivider = findViewById(R.id.viewPromptDivider)
        txtResponseContent = findViewById(R.id.txtResponseContent)
        layoutResponseActions = findViewById(R.id.layoutResponseActions)
        btnCopyResponse = findViewById(R.id.btnCopyResponse)
        btnSpeakResponse = findViewById(R.id.btnSpeakResponse)

        layoutTextInputRow = findViewById(R.id.layoutTextInputRow)
        editQueryInput = findViewById(R.id.editQueryInput)
        btnSendTextQuery = findViewById(R.id.btnSendTextQuery)
        btnToggleKeyboard = findViewById(R.id.btnToggleKeyboard)
        btnVisionSearch = findViewById(R.id.btnVisionSearch)
        btnMicAction = findViewById(R.id.btnMicAction)

        cardScreenContextPreview = findViewById(R.id.cardScreenContextPreview)
        imgScreenThumbnail = findViewById(R.id.imgScreenThumbnail)
        btnRemoveScreenContext = findViewById(R.id.btnRemoveScreenContext)

        chipNotifications = findViewById(R.id.chipNotifications)
        chipScreen = findViewById(R.id.chipScreen)
        chipNews = findViewById(R.id.chipNews)
        chipSchedule = findViewById(R.id.chipSchedule)
        chipSystem = findViewById(R.id.chipSystem)

        // Check if fresh screen context is attached
        initScreenContextPreview()
    }

    private fun initScreenContextPreview() {
        val bmp = com.assistant.athena.data.ScreenCaptureHolder.getScreenshot()
        if (bmp != null) {
            isScreenContextAttached = true
            imgScreenThumbnail.setImageBitmap(bmp)
            cardScreenContextPreview.visibility = View.VISIBLE
        } else {
            isScreenContextAttached = false
            cardScreenContextPreview.visibility = View.GONE
        }
    }

    private fun setupListeners() {
        viewDismissBackdrop.setOnClickListener { dismissWithAnimation() }

        // Screen Context Preview click handlers
        cardScreenContextPreview.setOnClickListener {
            triggerHaptic(VibrationEffect.EFFECT_CLICK)
            executeQuery("Analyze what's on my screen and summarize the key insights.")
        }

        btnRemoveScreenContext.setOnClickListener {
            triggerHaptic(VibrationEffect.EFFECT_CLICK)
            isScreenContextAttached = false
            com.assistant.athena.data.ScreenCaptureHolder.clear()
            cardScreenContextPreview.visibility = View.GONE
        }

        // Suggestion Chips (one-tap instant queries)
        chipNotifications.setOnClickListener { executeQuery("Catch me up on my notifications and recent messages") }
        chipScreen.setOnClickListener { executeQuery("What's currently on my screen? Provide key context and insights.") }
        chipNews.setOnClickListener { executeQuery("Perform deep research on today's breaking news and top headlines") }
        chipSchedule.setOnClickListener { executeQuery("Check my upcoming schedule, weather forecast, and reminders") }
        chipSystem.setOnClickListener { executeQuery("Run a full system diagnosis and report device status") }

        // Bottom Action Toolbar
        btnToggleKeyboard.setOnClickListener { toggleKeyboardMode() }
        btnVisionSearch.setOnClickListener {
            triggerHaptic(VibrationEffect.EFFECT_CLICK)
            executeQuery("Analyze screen context and assist with the active task.")
        }
        btnMicAction.setOnClickListener {
            if (isRecording) {
                stopAudioRecording()
            } else {
                startAudioRecording()
            }
        }

        // Send Text Query
        btnSendTextQuery.setOnClickListener {
            val query = editQueryInput.text.toString().trim()
            if (query.isNotEmpty()) {
                editQueryInput.text.clear()
                hideSoftKeyboard()
                executeQuery(query)
            }
        }

        editQueryInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                btnSendTextQuery.performClick()
                true
            } else false
        }

        // Response actions
        btnCopyResponse.setOnClickListener {
            val text = lastSpokenText.ifEmpty { txtResponseContent.text.toString() }
            if (text.isNotEmpty()) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("ATHENA Response", text))
                Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                triggerHaptic(VibrationEffect.EFFECT_CLICK)
            }
        }

        btnSpeakResponse.setOnClickListener {
            val text = lastSpokenText.ifEmpty { txtResponseContent.text.toString() }
            if (text.isNotEmpty()) {
                speakText(text)
            }
        }
    }

    private fun toggleKeyboardMode() {
        if (layoutTextInputRow.visibility == View.VISIBLE) {
            layoutTextInputRow.visibility = View.GONE
            hideSoftKeyboard()
        } else {
            stopAudioRecording()
            layoutTextInputRow.visibility = View.VISIBLE
            editQueryInput.requestFocus()
            val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showSoftInput(editQueryInput, InputMethodManager.SHOW_IMPLICIT)
        }
    }

    private fun hideSoftKeyboard() {
        val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(editQueryInput.windowToken, 0)
    }

    // =========================================================================
    // Real-Time SSE Stream Listener (Exactly like Web Application)
    // =========================================================================

    private fun connectSSEStream() {
        sseEventSource?.cancel()

        val request = Request.Builder()
            .url(STREAM_URL)
            .build()

        val factory = EventSources.createFactory(client)
        sseEventSource = factory.newEventSource(request, object : EventSourceListener() {

            override fun onOpen(eventSource: EventSource, response: Response) {
                Log.i(TAG, "SSE Stream connected to Termux backend")
            }

            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                handler.post {
                    handleBackendSSEEvent(type, data)
                }
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                Log.w(TAG, "SSE connection error: ${t?.message}")
                handler.postDelayed({
                    if (!isFinishing && !isDestroyed) {
                        connectSSEStream()
                    }
                }, 4000)
            }

            override fun onClosed(eventSource: EventSource) {
                Log.i(TAG, "SSE stream closed")
            }
        })
    }

    private fun handleBackendSSEEvent(type: String?, rawData: String) {
        try {
            val json = JSONObject(rawData)
            val eventType = type ?: json.optString("type", "")

            when (eventType) {
                "reply" -> {
                    val replyText = json.optString("text", "")
                    if (replyText.isNotEmpty()) {
                        lastSpokenText = replyText
                        showAssistantResponse(replyText)
                        triggerHaptic(VibrationEffect.EFFECT_TICK)

                        // Default voice output: Always speak assistant responses
                        speakText(replyText)
                    }
                }

                "phase" -> {
                    val phase = json.optString("phase", "")
                    when (phase) {
                        "processing" -> {
                            orbView.setState(OrbView.STATE_THINKING)
                            waveformVisualizer.setMode(listening = false, thinking = true, speaking = false)
                        }
                        "speaking" -> {
                            orbView.setState(OrbView.STATE_SPEAKING)
                            waveformVisualizer.setMode(listening = false, thinking = false, speaking = true)
                        }
                        "standby", "idle" -> {
                            orbView.setState(OrbView.STATE_LISTENING)
                            waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)
                            // Continuous conversation: automatically resume listening for user's next turn
                            if (!isRecording && !isFinishing && !isTtsSpeaking) {
                                handler.postDelayed({
                                    if (!isRecording && !isFinishing && !isTtsSpeaking) {
                                        startAudioRecording()
                                    }
                                }, 600)
                            }
                        }
                    }
                }

                "tool_start" -> {
                    val toolName = json.optString("name", "tool")
                    orbView.setState(OrbView.STATE_THINKING)
                    waveformVisualizer.setMode(listening = false, thinking = true, speaking = false)
                    showStatusTelemetry("⚡ <i>Executing ${cleanToolName(toolName)}…</i>")
                }

                "tool_end" -> {
                    val toolName = json.optString("name", "tool")
                    val duration = json.optInt("duration_ms", 0)
                    showStatusTelemetry("✓ <i>${cleanToolName(toolName)} finished (${duration}ms)</i>")
                }

                "snapshot" -> {
                    val phase = json.optString("phase", "")
                    val reply = json.optString("reply", "")
                    if (phase == "speaking" && reply.isNotEmpty() && lastSpokenText.isEmpty()) {
                        lastSpokenText = reply
                        orbView.setState(OrbView.STATE_SPEAKING)
                        waveformVisualizer.setMode(listening = false, thinking = false, speaking = true)
                        showAssistantResponse(reply)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse SSE event: $rawData", e)
        }
    }

    private fun cleanToolName(name: String): String {
        return when (name) {
            "duckduckgo_search" -> "Web Search"
            "deep_research" -> "Deep Research"
            "memory_search" -> "Memory Recall"
            "read_notes" -> "Notes Vault"
            "termux_command" -> "System Tools"
            else -> name.replace("_", " ").replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
        }
    }

    // =========================================================================
    // Query Execution & Prompt Dispatch (POST /prompt)
    // =========================================================================

    private fun executeQuery(promptText: String) {
        stopAudioRecording()
        lastSpokenText = ""

        showUserQuery(promptText)
        orbView.setState(OrbView.STATE_THINKING)
        waveformVisualizer.setMode(listening = false, thinking = true, speaking = false)

        val json = JSONObject().put("text", promptText)

        // Check if screen context is attached or prompt is asking for screen analysis
        val isScreenQuery = isScreenContextAttached || promptText.contains("screen", ignoreCase = true)
        if (isScreenQuery && com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()) {
            val imgB64 = com.assistant.athena.data.ScreenCaptureHolder.toBase64Jpeg()
            if (!imgB64.isNullOrEmpty()) {
                json.put("image_b64", imgB64)
                showStatusTelemetry("📸 <i>Uploading screen context to Gemini Vision…</i>")
            }
        }

        val jsonBody = json.toString()
        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(PROMPT_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                handler.post {
                    orbView.setState(OrbView.STATE_IDLE)
                    waveformVisualizer.setMode(listening = false, thinking = false, speaking = false)
                    showStatusTelemetry("⚠️ <i>Unable to reach Termux AI backend (127.0.0.1:2027)</i>")
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()

                handler.post {
                    try {
                        val json = JSONObject(body)
                        val ok = json.optBoolean("ok", false)
                        val handledSlash = json.optBoolean("handled_slash", false)
                        val directReply = json.optString("reply", "")

                        if (ok && handledSlash && directReply.isNotEmpty()) {
                            lastSpokenText = directReply
                            orbView.setState(OrbView.STATE_SPEAKING)
                            waveformVisualizer.setMode(listening = false, thinking = false, speaking = true)
                            showAssistantResponse(directReply)
                            speakText(directReply)
                        }
                    } catch (_: Exception) {}
                }
            }
        })
    }

    private fun showUserQuery(queryText: String) {
        cardResponseContainer.visibility = View.VISIBLE
        layoutUserPromptRow.visibility = View.VISIBLE
        txtUserPrompt.text = "“$queryText”"
        txtStatusTelemetry.visibility = View.VISIBLE
        txtStatusTelemetry.text = formatHtml("⚡ <i>Reasoning with AI…</i>")
        viewPromptDivider.visibility = View.VISIBLE
        txtResponseContent.visibility = View.GONE
        layoutResponseActions.visibility = View.GONE
        cardResponseContainer.post { cardResponseContainer.fullScroll(View.FOCUS_UP) }
    }

    private fun showStatusTelemetry(statusHtml: String) {
        cardResponseContainer.visibility = View.VISIBLE
        txtStatusTelemetry.visibility = View.VISIBLE
        txtStatusTelemetry.text = formatHtml(statusHtml)
        viewPromptDivider.visibility = View.VISIBLE
    }

    private fun showAssistantResponse(responseText: String) {
        cardResponseContainer.visibility = View.VISIBLE
        txtStatusTelemetry.visibility = View.GONE
        viewPromptDivider.visibility = View.VISIBLE
        txtResponseContent.visibility = View.VISIBLE
        txtResponseContent.text = formatHtml(formatMarkdown(responseText))
        layoutResponseActions.visibility = View.VISIBLE
        cardResponseContainer.post { cardResponseContainer.fullScroll(View.FOCUS_UP) }
    }

    private fun formatMarkdown(text: String): String {
        return text
            .replace(Regex("\\*\\*(.*?)\\*\\*"), "<b>$1</b>")
            .replace(Regex("`([^`]+)`"), "<tt>$1</tt>")
            .replace("\n", "<br/>")
    }

    private fun formatHtml(html: String): Spanned {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            Html.fromHtml(html, Html.FROM_HTML_MODE_COMPACT)
        } else {
            @Suppress("DEPRECATION")
            Html.fromHtml(html)
        }
    }

    // =========================================================================
    // Real-Time Audio Capture & Dynamic Waveform Reaction
    // =========================================================================

    @SuppressLint("MissingPermission")
    private fun startAudioRecording() {
        if (isRecording || isTtsSpeaking || SystemClock.uptimeMillis() < ttsQuietUntil) return
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                channelConfig,
                audioFormat,
                minBufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    sampleRate,
                    channelConfig,
                    audioFormat,
                    minBufferSize
                )
            }

            // Enable Hardware Acoustic Echo Cancellation and Noise Suppression
            val sessionId = audioRecord?.audioSessionId ?: 0
            if (sessionId != 0) {
                if (AcousticEchoCanceler.isAvailable()) {
                    try {
                        AcousticEchoCanceler.create(sessionId)?.enabled = true
                    } catch (_: Exception) {}
                }
                if (NoiseSuppressor.isAvailable()) {
                    try {
                        NoiseSuppressor.create(sessionId)?.enabled = true
                    } catch (_: Exception) {}
                }
            }

            audioRecord?.startRecording()
            isRecording = true

            orbView.setState(OrbView.STATE_LISTENING)
            waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)

            recordThread = Thread {
                val buffer = ShortArray(1024)
                val speechStream = ByteArrayOutputStream()
                var isVoiceActive = false
                var silenceFrames = 0
                var speechFrames = 0
                var noiseFloor = 400.0

                while (isRecording && !isFinishing) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0) {
                        // Guard against TTS speech audio bleeding into mic input
                        if (isTtsSpeaking || SystemClock.uptimeMillis() < ttsQuietUntil) {
                            isVoiceActive = false
                            speechFrames = 0
                            silenceFrames = 0
                            speechStream.reset()
                            continue
                        }

                        var sum = 0.0
                        for (i in 0 until read) {
                            sum += abs(buffer[i].toDouble())
                        }
                        val rms = sum / read

                        if (!isVoiceActive) {
                            noiseFloor = noiseFloor * 0.97 + rms * 0.03
                        }

                        val speechThreshold = maxOf(noiseFloor * 2.8, 1600.0)

                        if (rms > speechThreshold) {
                            silenceFrames = 0
                            speechFrames++
                            if (!isVoiceActive && speechFrames >= 4) {
                                isVoiceActive = true
                                speechStream.reset()
                            }
                        } else {
                            if (isVoiceActive) {
                                silenceFrames++
                                if (silenceFrames >= 13) {
                                    isVoiceActive = false
                                    speechFrames = 0
                                    val pcmData = speechStream.toByteArray()
                                    speechStream.reset()

                                    if (pcmData.size >= sampleRate * 0.45 * 2) {
                                        val wavData = addWavHeader(pcmData, sampleRate)
                                        handler.post {
                                            transcribeAndAsk(wavData)
                                        }
                                    }
                                }
                            }
                        }

                        val normLevel = if (isVoiceActive && rms > noiseFloor) {
                            ((rms - noiseFloor) / 2400.0).toFloat().coerceIn(0f, 1f)
                        } else 0.0f

                        handler.post {
                            waveformVisualizer.setMicLevel(normLevel)
                            orbView.setAudioAmplitude(normLevel)
                        }

                        if (isVoiceActive) {
                            val byteBuf = ByteArray(read * 2)
                            ByteBuffer.wrap(byteBuf).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(buffer, 0, read)
                            speechStream.write(byteBuf)
                        }
                    }
                }
            }.apply {
                priority = Thread.MAX_PRIORITY
                start()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start audio recording", e)
        }
    }

    private fun stopAudioRecording() {
        isRecording = false
        recordThread?.interrupt()
        recordThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    private fun transcribeAndAsk(wavBytes: ByteArray) {
        stopAudioRecording()
        orbView.setState(OrbView.STATE_THINKING)
        waveformVisualizer.setMode(listening = false, thinking = true, speaking = false)
        showStatusTelemetry("⚡ <i>Transcribing speech…</i>")

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
                runOnDeviceWhisper(wavBytes)
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()

                handler.post {
                    try {
                        val json = JSONObject(body)
                        val text = json.optString("text", "")
                        val cmd = json.optString("command", "")
                        val rawQuery = if (cmd.isNotEmpty()) cmd else text
                        val queryText = rawQuery.trim()

                        if (queryText.isNotEmpty()) {
                            // Filter out acoustic self-echo of previous AI response
                            if (isEchoOfLastReply(queryText, lastSpokenText)) {
                                Log.i(TAG, "Ignored acoustic echo of previous response: '$queryText'")
                                orbView.setState(OrbView.STATE_LISTENING)
                                waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)
                                handler.postDelayed({
                                    if (!isRecording && !isFinishing && !isTtsSpeaking) {
                                        startAudioRecording()
                                    }
                                }, 600)
                            } else {
                                executeQuery(queryText)
                            }
                        } else {
                            runOnDeviceWhisper(wavBytes)
                        }
                    } catch (_: Exception) {
                        runOnDeviceWhisper(wavBytes)
                    }
                }
            }
        })
    }

    private fun runOnDeviceWhisper(wavBytes: ByteArray) {
        CoroutineScope(Dispatchers.Main).launch {
            showStatusTelemetry("⚡ <i>Transcribing on-device with Whisper TFLite…</i>")
            val whisperText = WhisperOfflineTranscriber.transcribeAudio(
                this@AssistantOverlayActivity,
                wavBytes
            )
            if (whisperText.isNotEmpty()) {
                if (isEchoOfLastReply(whisperText, lastSpokenText)) {
                    Log.i(TAG, "Ignored acoustic echo of previous response: '$whisperText'")
                    orbView.setState(OrbView.STATE_LISTENING)
                    waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)
                    handler.postDelayed({
                        if (!isRecording && !isFinishing && !isTtsSpeaking) {
                            startAudioRecording()
                        }
                    }, 600)
                } else {
                    executeQuery(whisperText)
                }
            } else {
                orbView.setState(OrbView.STATE_IDLE)
                waveformVisualizer.setMode(listening = false, thinking = false, speaking = false)
            }
        }
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
        header[20] = 1; header[21] = 0 // PCM
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
    // Native Android TTS & Haptics (Supports Tamil & Multilingual Speech)
    // =========================================================================

    private fun initTTS() {
        tts = TextToSpeech(this, this)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    isTtsSpeaking = true
                    ttsQuietUntil = SystemClock.uptimeMillis() + 60000L
                    handler.post {
                        orbView.setState(OrbView.STATE_SPEAKING)
                        waveformVisualizer.setMode(listening = false, thinking = false, speaking = true)
                    }
                }

                override fun onDone(utteranceId: String?) {
                    isTtsSpeaking = false
                    ttsQuietUntil = SystemClock.uptimeMillis() + 1000L // 1.0s quiet grace period
                    handler.post {
                        orbView.setState(OrbView.STATE_LISTENING)
                        waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)
                    }
                    handler.postDelayed({
                        if (!isTtsSpeaking && !isRecording && !isFinishing) {
                            startAudioRecording()
                        }
                    }, 1000L)
                }

                override fun onError(utteranceId: String?) {
                    isTtsSpeaking = false
                    ttsQuietUntil = SystemClock.uptimeMillis() + 600L
                    handler.post {
                        orbView.setState(OrbView.STATE_LISTENING)
                        waveformVisualizer.setMode(listening = true, thinking = false, speaking = false)
                    }
                    handler.postDelayed({
                        if (!isTtsSpeaking && !isRecording && !isFinishing) {
                            startAudioRecording()
                        }
                    }, 600L)
                }
            })
            isTtsReady = true
            pendingSpeechText?.let { pending ->
                pendingSpeechText = null
                speakText(pending)
            }
        }
    }

    private fun speakText(text: String) {
        if (text.isBlank()) return
        if (!isTtsReady || tts == null) {
            pendingSpeechText = text
            return
        }
        stopAudioRecording()
        isTtsSpeaking = true
        ttsQuietUntil = SystemClock.uptimeMillis() + 60000L
        try {
            // Clean markdown syntax for natural speech synthesis
            val cleanText = text
                .replace(Regex("```[\\s\\S]*?```"), " ")
                .replace(Regex("`[^`]*`"), " ")
                .replace(Regex("\\[([^\\]]+)\\]\\([^\\)]+\\)"), "$1")
                .replace(Regex("[*#_~]"), " ")
                .replace(Regex("\\s+"), " ")
                .trim()
            val toSpeak = cleanText.ifEmpty { text }

            val hasTamil = toSpeak.any { it in '\u0B80'..'\u0BFF' }
            if (hasTamil) {
                val tamilLocale = Locale("ta", "IN")
                val res = tts?.setLanguage(tamilLocale)
                if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                    tts?.language = Locale("ta")
                }
            } else {
                tts?.language = Locale.US
            }
            val params = Bundle().apply {
                putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_MUSIC)
            }
            tts?.speak(toSpeak, TextToSpeech.QUEUE_FLUSH, params, "AthenaReply")
        } catch (e: Exception) {
            isTtsSpeaking = false
            ttsQuietUntil = SystemClock.uptimeMillis() + 500L
            Log.w(TAG, "Native TTS playback error", e)
        }
    }

    private fun isEchoOfLastReply(transcript: String, lastReply: String): Boolean {
        if (transcript.length < 2) return true
        if (lastReply.isEmpty()) return false
        val normTranscript = transcript.lowercase().replace(Regex("[^\\p{L}\\p{Nd}]+"), "")
        val normReply = lastReply.lowercase().replace(Regex("[^\\p{L}\\p{Nd}]+"), "")
        if (normTranscript.isEmpty() || normReply.isEmpty()) return false
        if (normReply.contains(normTranscript) && normTranscript.length > 8) return true
        if (normTranscript.contains(normReply) && normReply.length > 8) return true
        return false
    }

    private fun triggerHaptic(effectId: Int) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vm?.defaultVibrator?.vibrate(VibrationEffect.createPredefined(effectId))
            } else {
                @Suppress("DEPRECATION")
                val v = getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                @Suppress("DEPRECATION")
                v?.vibrate(30L)
            }
        } catch (_: Exception) {}
    }

    private fun hasAudioPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_RECORD &&
            grantResults.isNotEmpty() &&
            grantResults[0] == PackageManager.PERMISSION_GRANTED
        ) {
            startAudioRecording()
        }
    }

    private fun dismissWithAnimation() {
        stopAudioRecording()
        finish()
        overridePendingTransition(0, R.anim.slide_down_out)
    }

    override fun onBackPressed() {
        dismissWithAnimation()
    }

    override fun onDestroy() {
        stopAudioRecording()
        sseEventSource?.cancel()
        sseEventSource = null
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }
}
