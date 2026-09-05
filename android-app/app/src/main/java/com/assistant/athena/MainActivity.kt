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
                    },
                    dashboardContent = { onNavigateToChat ->
                        AthenaDashboardScreen(
                            status = status,
                            networkClient = networkClient,
                            onOpenOverlay = { launchOverlay() },
                            onOpenSettings = { openAssistantSettings() },
                            onOpenGuide = { openAccessGuide() },
                            onRefresh = {
                                coroutineScope.launch { refresh() }
                            },
                            onNavigateToChat = onNavigateToChat
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
    val model: String = "Gemini 3.5 Flash Lite"
)

@Composable
fun AthenaDashboardScreen(
    status: BackendStatus,
    networkClient: NetworkClient,
    onOpenOverlay: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenGuide: () -> Unit,
    onRefresh: () -> Unit,
    onNavigateToChat: (String?) -> Unit
) {
    var queryText by remember { mutableStateOf("") }
    var recentSessions by remember { mutableStateOf<List<SessionItem>>(emptyList()) }

    val infiniteTransition = rememberInfiniteTransition(label = "StatusPulse")
    val ledAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "ledAlpha"
    )

    LaunchedEffect(Unit) {
        try {
            val sessions = networkClient.fetchSessions()
            recentSessions = sessions.take(3)
        } catch (_: Exception) {}
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // ═══ 1. Perplexity Brand & Telemetry Header Bar ═══
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.clickable { onRefresh() }
            ) {
                Text(
                    text = "✳",
                    color = PerplexityTeal,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "ATHENA",
                    color = TextPrimary,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp,
                    fontFamily = FontFamily.SansSerif
                )
            }

            // Model & LED Status Capsule
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = PerplexitySurfaceElevated,
                border = BorderStroke(1.dp, PerplexityPillBorder),
                modifier = Modifier.clickable { onRefresh() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(7.dp)
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
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.5.sp,
                        fontFamily = FontFamily.Monospace
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "•",
                        color = TextMuted,
                        fontSize = 10.sp
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = status.model.replace("Gemini ", "Gemini-"),
                        color = TextSecondary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(36.dp))

        // ═══ 2. Center Perplexity Hero ═══
        Text(
            text = "✳",
            color = PerplexityTeal,
            fontSize = 38.sp,
            fontWeight = FontWeight.Light
        )
        Spacer(modifier = Modifier.height(10.dp))
        Text(
            text = "Where knowledge begins",
            color = TextPrimary,
            fontSize = 24.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = (-0.5).sp,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = "Search live intelligence, research deep queries, or inspect your screen",
            color = TextMuted,
            fontSize = 13.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 16.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        // ═══ 3. Primary Floating Search Capsule ═══
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(
                    elevation = 8.dp,
                    shape = RoundedCornerShape(22.dp),
                    ambientColor = PerplexityTealDim,
                    spotColor = PerplexityTealDim
                ),
            shape = RoundedCornerShape(22.dp),
            color = PerplexitySurfaceElevated,
            border = BorderStroke(1.dp, PerplexityPillBorder)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = "Search",
                        tint = TextMuted,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    TextField(
                        value = queryText,
                        onValueChange = { queryText = it },
                        placeholder = {
                            Text(
                                text = "Ask anything or search...",
                                color = TextMuted,
                                fontSize = 14.sp
                            )
                        },
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = Color.Transparent,
                            unfocusedContainerColor = Color.Transparent,
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary,
                            cursorColor = PerplexityTeal
                        ),
                        singleLine = false,
                        maxLines = 3,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = {
                            if (queryText.isNotBlank()) {
                                onNavigateToChat(queryText)
                            } else {
                                onNavigateToChat(null)
                            }
                        }),
                        modifier = Modifier.weight(1f)
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Left action icons
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(
                            onClick = onOpenOverlay,
                            modifier = Modifier.size(36.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Mic,
                                contentDescription = "Voice Input",
                                tint = PerplexityTeal,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        IconButton(
                            onClick = {
                                onNavigateToChat("Summarize the current visual screen context and inspect displayed interface.")
                            },
                            modifier = Modifier.size(36.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.CameraAlt,
                                contentDescription = "Screen Context",
                                tint = PerplexityTeal,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }

                    // Signature Circular Perplexity Send Button
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(
                                if (queryText.isNotBlank()) PerplexityTeal
                                else PerplexityTeal.copy(alpha = 0.5f)
                            )
                            .clickable {
                                if (queryText.isNotBlank()) {
                                    onNavigateToChat(queryText)
                                } else {
                                    onNavigateToChat(null)
                                }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowUpward,
                            contentDescription = "Search",
                            tint = VoidBlack,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        // ═══ 4. Focus Mode Quick Chips Row ═══
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FocusChip(
                label = "Web Search",
                icon = Icons.Default.Public,
                onClick = { onNavigateToChat("Search the web for ") }
            )
            FocusChip(
                label = "Pro Research",
                icon = Icons.Default.AutoAwesome,
                onClick = { onNavigateToChat("Conduct deep comprehensive research on ") }
            )
            FocusChip(
                label = "Screen Context",
                icon = Icons.Default.CameraAlt,
                onClick = { onNavigateToChat("Inspect current screen context: ") }
            )
            FocusChip(
                label = "Knowledge Vault",
                icon = Icons.Default.Folder,
                onClick = { onNavigateToChat("Search knowledge vault notes for ") }
            )
            FocusChip(
                label = "Security Recon",
                icon = Icons.Default.Security,
                onClick = { onNavigateToChat("Perform security audit on ") }
            )
        }

        Spacer(modifier = Modifier.height(28.dp))

        // ═══ 5. Recent Threads / Discovery Section ═══
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "RECENT THREADS",
                color = TextMuted,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 1.2.sp,
                fontFamily = FontFamily.Monospace
            )
            Text(
                text = "View all ›",
                color = PerplexityTeal,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier
                    .clickable { onNavigateToChat(null) }
                    .padding(vertical = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(10.dp))

        if (recentSessions.isNotEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                recentSessions.forEach { session ->
                    RecentThreadCard(
                        session = session,
                        onClick = { onNavigateToChat(null) }
                    )
                }
            }
        } else {
            // Discovery Starter Prompts
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                DiscoveryCard(
                    prompt = "Explain quantum computing and qubit superposition simply",
                    onClick = { onNavigateToChat("Explain quantum computing and qubit superposition simply") }
                )
                DiscoveryCard(
                    prompt = "Analyze system health, device battery, and background services",
                    onClick = { onNavigateToChat("Analyze system health, device battery, and background services") }
                )
                DiscoveryCard(
                    prompt = "Conduct a security audit of recent terminal commands",
                    onClick = { onNavigateToChat("Conduct a security audit of recent terminal commands") }
                )
            }
        }

        Spacer(modifier = Modifier.height(26.dp))

        // ═══ 6. Tactical Quick System Controls ═══
        Button(
            onClick = onOpenOverlay,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .shadow(
                    elevation = 6.dp,
                    shape = RoundedCornerShape(16.dp),
                    ambientColor = PerplexityTealDim,
                    spotColor = PerplexityTealDim
                ),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = PerplexityTeal,
                contentColor = VoidBlack
            )
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Text(
                    text = "⚡",
                    fontSize = 16.sp,
                    color = VoidBlack
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "OPEN ASSISTANT HUD",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp,
                    fontFamily = FontFamily.SansSerif,
                    color = VoidBlack
                )
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
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

        Spacer(modifier = Modifier.height(24.dp))

        // ═══ 7. Perplexity Footer Telemetry ═══
        Text(
            text = "127.0.0.1:2027 // STREAMING SSE ENGINE",
            color = TextMuted,
            fontSize = 10.5.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 1.2.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(12.dp))
    }
}

@Composable
fun FocusChip(
    label: String,
    icon: ImageVector,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = PerplexitySurfaceElevated,
        border = BorderStroke(1.dp, PerplexityPillBorder),
        modifier = Modifier.clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = PerplexityTeal,
                modifier = Modifier.size(14.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = label,
                color = TextSecondary,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

@Composable
fun RecentThreadCard(
    session: SessionItem,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PerplexityPillBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "💬",
                    fontSize = 14.sp
                )
                Spacer(modifier = Modifier.width(10.dp))
                Column {
                    Text(
                        text = session.title,
                        color = TextPrimary,
                        fontSize = 13.5.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (session.lastMessage.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = session.lastMessage,
                            color = TextMuted,
                            fontSize = 11.5.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            Surface(
                color = PanelDarkSolid,
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, PerplexityPillBorder)
            ) {
                Text(
                    text = "${session.messageCount} msgs",
                    color = TextMuted,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                )
            }
        }
    }
}

@Composable
fun DiscoveryCard(
    prompt: String,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PerplexityPillBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "💡",
                    fontSize = 14.sp
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = prompt,
                    color = TextSecondary,
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Icon(
                imageVector = Icons.Default.ArrowForward,
                contentDescription = null,
                tint = PerplexityTeal,
                modifier = Modifier.size(16.dp)
            )
        }
    }
}

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
            .height(76.dp)
            .clip(RoundedCornerShape(14.dp))
            .border(
                border = BorderStroke(1.dp, PerplexityPillBorder),
                shape = RoundedCornerShape(14.dp)
            )
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
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
                    tint = PerplexityTeal,
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
