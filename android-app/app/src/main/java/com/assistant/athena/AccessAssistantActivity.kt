package com.assistant.athena

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity

/**
 * Access Assistant Guide Screen.
 * Visual guide explaining how to invoke ATHENA via Power button, Home button, or Corner swipe,
 * with 1-tap navigation to Android Default Assistant Settings.
 */
class AccessAssistantActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_access_assistant)

        findViewById<ImageView>(R.id.btnCloseAccessGuide).setOnClickListener {
            finish()
        }

        findViewById<Button>(R.id.btnSetDefaultAssistant).setOnClickListener {
            openDefaultAssistantSettings()
        }

        findViewById<Button>(R.id.btnTryAssistantNow).setOnClickListener {
            val intent = Intent(this, AssistantOverlayActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            startActivity(intent)
        }
    }

    private fun openDefaultAssistantSettings() {
        try {
            val intent = Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
            startActivity(intent)
        } catch (_: Exception) {
            try {
                val intent = Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
                startActivity(intent)
            } catch (_: Exception) {
                val intent = Intent(Settings.ACTION_SETTINGS)
                startActivity(intent)
            }
        }
    }
}
