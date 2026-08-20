package com.assistant.athena

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/**
 * Handles the system ASSIST intent (e.g. holding home button or assistant gesture).
 */
class AssistActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("assist_invoked", true)
        }
        startActivity(intent)
        finish()
    }
}
