package com.assistant.athena

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.speech.RecognitionService
import android.util.Log

/**
 * Android Digital Assistant Service for A.T.H.E.N.A.
 *
 * This allows ATHENA to be selected as the system-level Default Digital Assistant
 * in Android Settings -> Apps -> Default Apps -> Digital Assistant App,
 * replacing Google Assistant when the user holds the Home button, long-presses Power,
 * or triggers assistant shortcuts.
 */
class AthenaVoiceInteractionService : VoiceInteractionService() {

    companion object {
        private const val TAG = "Athena.VoiceInteraction"
    }

    override fun onReady() {
        super.onReady()
        Log.i(TAG, "ATHENA VoiceInteractionService is ready and active as default assistant")
    }

    override fun onShutdown() {
        Log.i(TAG, "ATHENA VoiceInteractionService shutdown")
        super.onShutdown()
    }
}

class AthenaVoiceSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession {
        return AthenaVoiceSession(this)
    }
}

class AthenaVoiceSession(context: android.content.Context) : VoiceInteractionSession(context) {
    override fun onHandleAssist(data: Bundle?, structure: android.app.assist.AssistStructure?, content: android.app.assist.AssistContent?) {
        super.onHandleAssist(data, structure, content)
        // When assistant is triggered by user gesture (power button / swipe / home button):
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("trigger_voice", true)
        }
        context.startActivity(intent)
        finish()
    }
}

class AthenaRecognitionService : RecognitionService() {
    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        // Recognition delegate
    }

    override fun onCancel(listener: Callback?) {}
    override fun onStopListening(listener: Callback?) {}
}
