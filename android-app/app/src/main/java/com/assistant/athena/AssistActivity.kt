package com.assistant.athena

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/**
 * Handles the system ASSIST intent (e.g. holding home button, long-pressing power button, or corner swipe gesture).
 * Instantly launches the Perplexity-style AssistantOverlayActivity without switching tasks or opening the previous app.
 */
class AssistActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val intent = Intent(this, AssistantOverlayActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION
            putExtra("assist_invoked", true)
        }
        startActivity(intent)
        overridePendingTransition(0, 0)
        finish()
    }
}
