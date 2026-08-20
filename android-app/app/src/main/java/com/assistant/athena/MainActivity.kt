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
import android.view.View
import android.widget.Button
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * A.T.H.E.N.A. Dashboard — Control center for the 24/7 voice bridge.
 *
 * Features:
 *  - Start/Stop the background voice service
 *  - Backend connection health check
 *  - Permission status display
 *  - Auto-start on boot toggle
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "Athena.Main"
        private const val PERMISSION_REQUEST_CODE = 101
        private const val BACKEND_STATE_URL = "http://127.0.0.1:2027/state"
    }

    // UI elements
    private lateinit var txtTitle: TextView
    private lateinit var txtSubtitle: TextView
    private lateinit var txtServiceStatus: TextView
    private lateinit var txtBackendStatus: TextView
    private lateinit var txtPermissionStatus: TextView
    private lateinit var btnToggleService: Button
    private lateinit var btnCheckBackend: Button
    private lateinit var switchAutoStart: Switch

    private var isServiceRunning = false

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Bind views
        txtTitle = findViewById(R.id.txtTitle)
        txtSubtitle = findViewById(R.id.txtSubtitle)
        txtServiceStatus = findViewById(R.id.txtServiceStatus)
        txtBackendStatus = findViewById(R.id.txtBackendStatus)
        txtPermissionStatus = findViewById(R.id.txtPermissionStatus)
        btnToggleService = findViewById(R.id.btnToggleService)
        btnCheckBackend = findViewById(R.id.btnCheckBackend)
        switchAutoStart = findViewById(R.id.switchAutoStart)

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

        btnCheckBackend.setOnClickListener {
            checkBackendHealth()
        }

        switchAutoStart.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean("auto_start_on_boot", isChecked).apply()
        }

        // Initial status check
        updatePermissionStatus()
        checkBackendHealth()
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
                    txtBackendStatus.text = "🔴  Backend OFFLINE — Start Termux: python main.py"
                    txtBackendStatus.setTextColor(Color.parseColor("#E53935"))
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: "{}"
                response.close()
                runOnUiThread {
                    try {
                        val json = org.json.JSONObject(body)
                        val online = json.optBoolean("online", false)
                        val phase = json.optString("phase", "unknown")
                        val llmModel = json.optString("llm_model", "unknown")
                        if (online) {
                            txtBackendStatus.text = "🟢  Backend ONLINE — $llmModel ($phase)"
                            txtBackendStatus.setTextColor(Color.parseColor("#4CAF50"))
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
            append(" Microphone   ")
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
