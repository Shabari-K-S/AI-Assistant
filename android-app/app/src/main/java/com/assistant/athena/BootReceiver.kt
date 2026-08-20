package com.assistant.athena

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * Auto-starts the ATHENA Voice Bridge service when the device finishes booting.
 *
 * Combined with Termux:Boot auto-starting the Python backend, this ensures the
 * entire AI assistant system comes online automatically after a reboot with
 * zero user intervention.
 *
 * Requires: android.permission.RECEIVE_BOOT_COMPLETED
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "Athena.Boot"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED ||
            intent.action == "android.intent.action.QUICKBOOT_POWERON"
        ) {
            Log.i(TAG, "═══ Boot completed — starting ATHENA Voice Bridge ═══")

            // Check if auto-start is enabled in SharedPreferences
            val prefs = context.getSharedPreferences("athena_prefs", Context.MODE_PRIVATE)
            val autoStart = prefs.getBoolean("auto_start_on_boot", true)

            if (!autoStart) {
                Log.i(TAG, "Auto-start disabled in settings — skipping")
                return
            }

            val serviceIntent = Intent(context, VoiceBridgeService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent)
                } else {
                    context.startService(serviceIntent)
                }
                Log.i(TAG, "ATHENA Voice Bridge started successfully on boot")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start ATHENA on boot", e)
            }
        }
    }
}
