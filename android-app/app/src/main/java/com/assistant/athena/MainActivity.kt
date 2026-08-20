package com.assistant.athena

import android.Manifest
import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.util.Log
import android.widget.Button
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.*
import java.util.concurrent.TimeUnit

/**
 * A.T.H.E.N.A. Dashboard — Control center for the 24/7 voice bridge.
 *
 * Features:
 *  - Start/Stop the background voice service
 *  - Backend connection health check
 *  - Live activity log feed showing real-time speech and answers
 *  - Instant Test Voice Uplink button
 *  - Permission status display
 *  - Auto-start on boot toggle
 */
class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "Athena.Main"
        private const val PERMISSION_REQUEST_CODE = 101
        private const val BACKEND_STATE_URL = "http://127.0.0.1:2027/state"
        private const val BACKEND_ASK_URL = "http://127.0.0.1:2027/ask"
        const val ACTION_LOG_UPDATE = "com.assistant.athena.LOG_UPDATE"
        const val EXTRA_LOG_TEXT = "log_text"
    }

    // UI elements
    private lateinit var txtTitle: TextView
    private lateinit var txtSubtitle: TextView
    private lateinit var txtServiceStatus: TextView
    private lateinit var txtLiveLog: TextView
    private lateinit var txtBackendStatus: TextView
    private lateinit var txtPermissionStatus: TextView
    private lateinit var btnToggleService: Button
    private lateinit var btnTestQuery: Button
    private lateinit var btnCheckBackend: Button
    private lateinit var switchAutoStart: Switch

    private var isServiceRunning = false
    private var localTts: TextToSpeech? = null
    private var localTtsReady = false

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    // Broadcast receiver for live activity logs from the service
    private val logReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val logText = intent?.getStringExtra(EXTRA_LOG_TEXT)
            if (!logText.isNullOrEmpty()) {
                appendLog(logText)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Bind views
        txtTitle = findViewById(R.id.txtTitle)
        txtSubtitle = findViewById(R.id.txtSubtitle)
        txtServiceStatus = findViewById(R.id.txtServiceStatus)
        txtLiveLog = findViewById(R.id.txtLiveLog)
        txtBackendStatus = findViewById(R.id.txtBackendStatus)
        txtPermissionStatus = findViewById(R.id.txtPermissionStatus)
        btnToggleService = findViewById(R.id.btnToggleService)
        btnTestQuery = findViewById(R.id.btnTestQuery)
        btnCheckBackend = findViewById(R.id.btnCheckBackend)
        switchAutoStart = findViewById(R.id.switchAutoStart)

        localTts = TextToSpeech(this, this)

        // Check and request permissions
        checkAndRequestPermissions()
        requestBatteryOptimizationExemption()

        // Load auto-start preference
        val prefs = getSharedPreferences("athena_prefs", Context.MODE_PRIVATE)
        switchAutoStart.isChecked = prefs.getBoolean("auto_start_on_boot", true)

        // --- Event handlers ---

        btnToggleService.setOnClickListener {
            if (!isServiceRunning) {
                startVoiceService()
            } else {
                stopVoiceService()
            }
        }

        btnTestQuery.setOnClickListener {
            runTestQuery()
        }

        btnCheckBackend.setOnClickListener {
            checkBackendHealth()
        }

        switchAutoStart.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("auto_start_on_boot", isChecked).apply()
        }

        // Register broadcast receiver for live log feed
        val filter = IntentFilter(ACTION_LOG_UPDATE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(logReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(logReceiver, filter)
        }

        // Initial status checks
        updatePermissionStatus()
        checkBackendHealth()
    }

    override fun onDestroy() {
        try { unregisterReceiver(logReceiver) } catch (_: Exception) {}
        localTts?.stop()
        localTts?.shutdown()
        super.onDestroy()
    }

    private fun appendLog(line: String) {
        runOnUiThread {
            val current = txtLiveLog.text.toString()
            val lines = current.split("\n").takeLast(5).toMutableList()
            lines.add("• $line")
            txtLiveLog.text = lines.joinToString("\n")
        }
    }

    // =========================================================================
    // Test Voice Uplink
    // =========================================================================

    private fun runTestQuery() {
        val testPrompt = "Hello Athena, what is the system status and time?"
        appendLog("⚡ Sending test query: '$testPrompt'")
        btnTestQuery.isEnabled = false
        btnTestQuery.text = "⏳ Contacting Termux AI..."

        val jsonBody = JSONObject().put("text", testPrompt).toString()
        val requestBody = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(BACKEND_ASK_URL)
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    appendLog("❌ Uplink failed: ${e.message}")
                    btnTestQuery.isEnabled = true
                    btnTestQuery.text = "⚡  Test Voice Uplink"
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()
                runOnUiThread {
                    btnTestQuery.isEnabled = true
                    btnTestQuery.text = "⚡  Test Voice Uplink"
                    try {
                        val json = JSONObject(body)
                        val ok = json.optBoolean("ok", false)
                        val reply = json.optString("reply", "")
                        if (ok && reply.isNotEmpty()) {
                            appendLog("🤖 Termux Reply: \"$reply\"")
                            if (localTtsReady) {
                                localTts?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "test_reply")
                            }
                        } else {
                            val err = json.optString("error", "Unknown error")
                            appendLog("⚠️ Termux: $err")
                        }
                    } catch (e: Exception) {
                        appendLog("⚠️ Parse error: ${e.message}")
                    }
                }
            }
        })
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            localTts?.language = Locale.US
            localTtsReady = true
        }
    }

    // =========================================================================
    // Service Control
    // =========================================================================

    private fun startVoiceService() {
        if (!hasRequiredPermissions()) {
            checkAndRequestPermissions()
            return
        }

        val serviceIntent = Intent(this, VoiceBridgeService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            isServiceRunning = true
            updateServiceUI(true)
            appendLog("🟢 Voice Bridge service activated (24/7 background listening)")
            Log.i(TAG, "Voice Bridge service started")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start service", e)
            txtServiceStatus.text = "❌ Failed to start: ${e.message}"
        }
    }

    private fun stopVoiceService() {
        val serviceIntent = Intent(this, VoiceBridgeService::class.java)
        stopService(serviceIntent)
        isServiceRunning = false
        updateServiceUI(false)
        appendLog("🔴 Voice Bridge service stopped")
        Log.i(TAG, "Voice Bridge service stopped")
    }

    private fun updateServiceUI(running: Boolean) {
        if (running) {
            txtServiceStatus.text = "🟢  Voice Bridge: ACTIVE (24/7)"
            txtServiceStatus.setTextColor(Color.parseColor("#4CAF50"))
            btnToggleService.text = "⏹  Stop ATHENA"
            btnToggleService.setBackgroundColor(Color.parseColor("#E53935"))
        } else {
            txtServiceStatus.text = "🔴  Voice Bridge: STOPPED"
            txtServiceStatus.setTextColor(Color.parseColor("#E53935"))
            btnToggleService.text = "▶  Start ATHENA"
            btnToggleService.setBackgroundColor(Color.parseColor("#4CAF50"))
        }
    }

    // =========================================================================
    // Backend Health Check
    // =========================================================================

    private fun checkBackendHealth() {
        txtBackendStatus.text = "⏳  Checking Termux backend..."
        txtBackendStatus.setTextColor(Color.parseColor("#FF9800"))

        val request = Request.Builder()
            .url(BACKEND_STATE_URL)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    txtBackendStatus.text = "🔴  Backend OFFLINE — Start in Termux: bash scripts/daemon_watchdog.sh"
                    txtBackendStatus.setTextColor(Color.parseColor("#E53935"))
                    appendLog("⚠️ Termux backend offline at 127.0.0.1:2027")
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()
                runOnUiThread {
                    try {
                        val json = JSONObject(body)
                        val online = json.optBoolean("online", false)
                        val phase = json.optString("phase", "unknown")
                        val llmModel = json.optString("llm_model", "unknown")
                        if (online) {
                            txtBackendStatus.text = "🟢  Backend ONLINE — $llmModel ($phase)"
                            txtBackendStatus.setTextColor(Color.parseColor("#4CAF50"))
                            appendLog("✅ Connected to Termux AI Backend ($llmModel)")
                        } else {
                            txtBackendStatus.text = "🟡  Backend connected but not ready"
                            txtBackendStatus.setTextColor(Color.parseColor("#FF9800"))
                        }
                    } catch (e: Exception) {
                        txtBackendStatus.text = "🟡  Backend responded but unexpected format"
                        txtBackendStatus.setTextColor(Color.parseColor("#FF9800"))
                    }
                }
            }
        })
    }

    // =========================================================================
    // Permissions
    // =========================================================================

    private fun hasRequiredPermissions(): Boolean {
        val mic = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
        return mic == PackageManager.PERMISSION_GRANTED
    }

    private fun checkAndRequestPermissions() {
        val needed = mutableListOf<String>()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            needed.add(Manifest.permission.RECORD_AUDIO)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                needed.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), PERMISSION_REQUEST_CODE)
        }
    }

    @SuppressLint("BatteryLife")
    private fun requestBatteryOptimizationExemption() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                } catch (e: Exception) {
                    Log.w(TAG, "Could not request battery optimization exemption", e)
                }
            }
        }
    }

    private fun updatePermissionStatus() {
        val mic = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
        val notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                    PackageManager.PERMISSION_GRANTED
        } else true
        val battery = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            (getSystemService(Context.POWER_SERVICE) as PowerManager)
                .isIgnoringBatteryOptimizations(packageName)
        } else true

        val status = buildString {
            append(if (mic) "✅" else "❌")
            append(" Mic   ")
            append(if (notification) "✅" else "❌")
            append(" Notifications   ")
            append(if (battery) "✅" else "⚠️")
            append(" Battery Exempt")
        }
        txtPermissionStatus.text = status
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            updatePermissionStatus()
        }
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
    }
}
