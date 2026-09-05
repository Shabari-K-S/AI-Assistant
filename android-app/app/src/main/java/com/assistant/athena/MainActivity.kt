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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Gesture
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.TouchApp
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.assistant.athena.ui.components.DotMatrixBackground
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.components.NeuralArcReactor
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
                    },
                    dashboardContent = {
                        AthenaDashboardScreen(
                            status = status,
                            onOpenOverlay = { launchOverlay() },
                            onOpenSettings = { openAssistantSettings() },
                            onOpenGuide = { openAccessGuide() },
                            onRefresh = {
                                coroutineScope.launch { refresh() }
                            }
                        )
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
    val model: String = "Gemini 2.5 Flash"
)

@Composable
fun AthenaDashboardScreen(
    status: BackendStatus,
    onOpenOverlay: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenGuide: () -> Unit,
    onRefresh: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
            Spacer(modifier = Modifier.height(12.dp))

            // ═══ 1. JARVIS Central Arc Reactor & Neural Core ═══
            NeuralArcReactor(
                isOnline = status.isOnline
            )

            Spacer(modifier = Modifier.height(28.dp))

            // ═══ 2. Glassmorphism HUD Telemetry Card ═══
            HudTelemetryCard(
                status = status,
                onRefresh = onRefresh
            )

            Spacer(modifier = Modifier.height(20.dp))

            // ═══ 3. Primary Next-Gen Action: ⚡ OPEN ASSISTANT HUD ═══
            Button(
                onClick = onOpenOverlay,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .shadow(
                        elevation = 8.dp,
                        shape = RoundedCornerShape(14.dp),
                        ambientColor = NeonCyanGlow,
                        spotColor = NeonCyan
                    ),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = NeonCyan,
                    contentColor = VoidBlack
                ),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = "⚡",
                        fontSize = 18.sp,
                        color = VoidBlack
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "OPEN ASSISTANT HUD",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp,
                        fontFamily = FontFamily.SansSerif,
                        color = VoidBlack
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // ═══ 4. Secondary Action Tiles: CONFIG & GESTURES ═══
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                ActionTile(
                    title = "CONFIG",
                    subtitle = "Default App",
                    icon = Icons.Default.Settings,
                    modifier = Modifier.weight(1f),
                    onClick = onOpenSettings
                )
                ActionTile(
                    title = "GESTURES",
                    subtitle = "Power / Swipe",
                    icon = Icons.Default.TouchApp,
                    modifier = Modifier.weight(1f),
                    onClick = onOpenGuide
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ═══ 5. Integrated Capabilities Log ═══
            CapabilitiesLogCard()

            Spacer(modifier = Modifier.height(24.dp))

            // ═══ 6. Modern Footer Telemetry ═══
            Text(
                text = "127.0.0.1:2027 // TERMUX HUD LINK",
                color = TextMuted,
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                letterSpacing = 1.2.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(12.dp))
        }
}

/**
 * Translucent Glassmorphism Telemetry Card with Animated LED Status Indicator.
 */
@Composable
fun HudTelemetryCard(
    status: BackendStatus,
    onRefresh: () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "LedPulse")
    val ledAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "ledAlpha"
    )

    HudCard {
        // Digital Assistant Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "DIGITAL ASSISTANT",
                color = TextMuted,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 1.sp,
                fontFamily = FontFamily.Monospace
            )
            Text(
                text = "NATIVE TRIGGERS READY",
                color = NeonCyan,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.SansSerif
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        // AI Engine Backend Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "AI ENGINE BACKEND",
                color = TextMuted,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 1.sp,
                fontFamily = FontFamily.Monospace
            )

            Row(verticalAlignment = Alignment.CenterVertically) {
                // Animated Pulsing LED
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(
                            if (status.isOnline) NeonGreen.copy(alpha = ledAlpha)
                            else NeonAmber.copy(alpha = ledAlpha)
                        )
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = if (status.isOnline) "ONLINE" else "STANDBY",
                    color = if (status.isOnline) NeonGreen else NeonAmber,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // Telemetry Specs
        Text(
            text = "Model: ${status.model}  •  Port: 2027  •  Phase: ${status.phase}",
            color = TextSecondary,
            fontSize = 11.5.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(10.dp))

        // Refresh Connection Link
        Text(
            text = "› REFRESH CONNECTION",
            color = NeonCyan,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = onRefresh
                )
                .padding(vertical = 4.dp)
        )
    }
}

/**
 * Cyberpunk Action Tile with frosted glass backdrop and neon cyan stroke.
 */
@Composable
fun ActionTile(
    title: String,
    subtitle: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Surface(
        modifier = modifier
            .height(84.dp)
            .clip(RoundedCornerShape(14.dp))
            .border(
                border = BorderStroke(1.dp, PanelStroke),
                shape = RoundedCornerShape(14.dp)
            )
            .clickable(onClick = onClick),
        color = PanelDark,
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.Start
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = title,
                    tint = NeonCyan,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = title,
                    color = TextPrimary,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp,
                    fontFamily = FontFamily.SansSerif
                )
            }
            Spacer(modifier = Modifier.height(3.dp))
            Text(
                text = subtitle,
                color = TextMuted,
                fontSize = 10.5.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}

/**
 * Terminal-style Integrated Capabilities Log Card.
 */
@Composable
fun CapabilitiesLogCard() {
    HudCard {
        Text(
            text = "INTEGRATED CAPABILITIES",
            color = TextMuted,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 1.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(10.dp))

        val capabilities = listOf(
            "Real-Time Streaming SSE Link (Live AI Reasoning)",
            "Hardware Power & Home Button Long-Press",
            "Corner Gesture Navigation Invocation",
            "Continuous Conversational Turn Listening",
            "Live Dynamic Audio Waveform Spectrum",
            "Zero Background Battery Drain"
        )

        capabilities.forEach { item ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 3.dp),
                verticalAlignment = Alignment.Top
            ) {
                Text(
                    text = "›",
                    color = NeonCyan,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = item,
                    color = TextSecondary,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    fontFamily = FontFamily.SansSerif
                )
            }
        }
    }
}
