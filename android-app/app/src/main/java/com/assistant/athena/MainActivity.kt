package com.assistant.athena

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.assistant.athena.data.SessionItem
import com.assistant.athena.ui.components.DotMatrixBackground
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.ui.CyberpunkAppShell
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Principal Android UI/UX Engineer Implementation:
 * Cyberpunk JARVIS-meets-Perplexity Neural AI Dashboard in Jetpack Compose (Material 3).
 */
class MainActivity : ComponentActivity() {

    private val requestAudioPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* Permission result handled */ }

    private lateinit var networkClient: NetworkClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        networkClient = NetworkClient.getInstance(this)
        checkAudioPermission()

        setContent {
            AthenaTheme {
                var status by remember { mutableStateOf(BackendStatus()) }
                val coroutineScope = rememberCoroutineScope()

                suspend fun refresh() {
                    val (online, phase, model) = networkClient.checkHealth()
                    status = BackendStatus(isOnline = online, phase = phase, model = model)
                }

                LaunchedEffect(Unit) {
                    refresh()
                }

                CyberpunkAppShell(
                    networkClient = networkClient,
                    status = status,
                    onOpenOverlay = { launchOverlay() },
                    onOpenSettings = { openAssistantSettings() },
                    onOpenGuide = { openAccessGuide() },
                    onRefreshStatus = {
                        coroutineScope.launch { refresh() }
                    }
                )
            }
        }
    }

    private fun checkAudioPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestAudioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun launchOverlay() {
        triggerHaptic(VibrationEffect.EFFECT_CLICK)
        val intent = Intent(this, AssistantOverlayActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION
        }
        startActivity(intent)
    }

    private fun openAssistantSettings() {
        triggerHaptic(VibrationEffect.EFFECT_CLICK)
        try {
            startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS))
        } catch (_: Exception) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS))
            } catch (_: Exception) {
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
        }
    }

    private fun openAccessGuide() {
        triggerHaptic(VibrationEffect.EFFECT_CLICK)
        startActivity(Intent(this, AccessAssistantActivity::class.java))
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
                v?.vibrate(25L)
            }
        } catch (_: Exception) {}
    }
}

data class BackendStatus(
    val isOnline: Boolean = false,
    val phase: String = "checking",
    val model: String = "Gemini 3.5 Flash Lite"
)
