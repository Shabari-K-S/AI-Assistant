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
 * Allows ATHENA to be selected as the system-level Default Digital Assistant
 * in Android Settings -> Apps -> Default Apps -> Digital Assistant App.
 * When the user holds the Home button, long-presses Power, or swipes from corners,
 * this service immediately brings up the Perplexity-styled Assistant Overlay.
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
    override fun onHandleScreenshot(screenshot: android.graphics.Bitmap?) {
        super.onHandleScreenshot(screenshot)
        if (screenshot != null) {
            com.assistant.athena.data.ScreenCaptureHolder.setScreenshot(screenshot)
            Log.i("Athena.VoiceSession", "Received system screenshot: ${screenshot.width}x${screenshot.height}")
        }
    }

    override fun onHandleAssist(data: Bundle?, structure: android.app.assist.AssistStructure?, content: android.app.assist.AssistContent?) {
        super.onHandleAssist(data, structure, content)
        val hasScreen = com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()
        val intent = Intent(context, AssistantOverlayActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION
            putExtra("trigger_voice", true)
            putExtra("has_screen_context", hasScreen)
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
