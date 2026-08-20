package com.assistant.athena

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * A.T.H.E.N.A. Dashboard — Control center for the 24/7 voice bridge.
 *
 * Speech is handled exclusively by Termux Python TTS (no duplicate Android speech).
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "Athena.Main"
        private const val PERMISSION_REQUEST_CODE = 101
        private const val BACKEND_STATE_URL = "http://127.0.0.1:2027/state"
        private const val BACKEND_ASK_URL = "http://127.0.0.1:2027/ask"
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
    private lateinit var btnSetDefaultAssistant: Button
    private lateinit var btnCheckBackend: Button
    private lateinit var switchAutoStart: SwitchCompat

    private var isServiceRunning = false

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
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
            btnSetDefaultAssistant = findViewById(R.id.btnSetDefaultAssistant)
            btnCheckBackend = findViewById(R.id.btnCheckBackend)
            switchAutoStart = findViewById(R.id.switchAutoStart)

            // Ensure all phone audio streams are unmuted
            val am = getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && am != null) {
                try {
                    am.adjustStreamVolume(android.media.AudioManager.STREAM_MUSIC, android.media.AudioManager.ADJUST_UNMUTE, 0)
                    am.adjustStreamVolume(android.media.AudioManager.STREAM_NOTIFICATION, android.media.AudioManager.ADJUST_UNMUTE, 0)
                    am.adjustStreamVolume(android.media.AudioManager.STREAM_ALARM, android.media.AudioManager.ADJUST_UNMUTE, 0)
                    am.adjustStreamVolume(android.media.AudioManager.STREAM_SYSTEM, android.media.AudioManager.ADJUST_UNMUTE, 0)
                } catch (_: Exception) {}
            }

            // Attach log listener to VoiceBridgeService
            VoiceBridgeService.onLogListener = { msg ->
                appendLog(msg)
            }

            // Check and request permissions
            checkAndRequestPermissions()
            requestBatteryOptimizationExemption()

            // Load auto-start preference
            val prefs = getSharedPreferences("athena_prefs", Context.MODE_PRIVATE)
            switchAutoStart.isChecked = prefs.getBoolean("auto_start_on_boot", true)

            // Event handlers
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

            btnSetDefaultAssistant.setOnClickListener {
                try {
                    val intent = Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
                    startActivity(intent)
                } catch (e: Exception) {
                    try {
                        val intent = Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
                        startActivity(intent)
                    } catch (_: Exception) {
                        val intent = Intent(Settings.ACTION_SETTINGS)
                        startActivity(intent)
                    }
                }
            }

            btnCheckBackend.setOnClickListener {
                checkBackendHealth()
            }

            switchAutoStart.setOnCheckedChangeListener { _, isChecked ->
                prefs.edit().putBoolean("auto_start_on_boot", isChecked).apply()
            }

            updatePermissionStatus()
            checkBackendHealth()
        } catch (e: Exception) {
            Log.e(TAG, "Fatal error in onCreate", e)
        }
    }

    override fun onDestroy() {
        VoiceBridgeService.onLogListener = null
        super.onDestroy()
    }

    private fun appendLog(line: String) {
        runOnUiThread {
            try {
                val current = txtLiveLog.text.toString()
                val lines = current.split("\n").takeLast(5).toMutableList()
                lines.add("• $line")
                txtLiveLog.text = lines.joinToString("\n")
            } catch (_: Exception) {}
        }
    }

    // =========================================================================
    // Test Voice Uplink (Triggers Termux Python TTS)
    // =========================================================================

    private fun runTestQuery() {
        val testPrompt = "Hello Athena, what is the system status and time?"
        appendLog("⚡ Sending test query to Termux: '$testPrompt'")
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
                            appendLog("🤖 Termux Speaking: \"$reply\"")
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
            appendLog("🟢 Voice Bridge active (Termux TTS mode)")
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
