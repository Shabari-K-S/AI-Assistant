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
    var selectedTopMode by remember { mutableIntStateOf(0) } // 0: Search, 1: Computer/AI

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(VoidBlack)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // ═══ 1. Top Bar (Matching Screenshot 1) ═══
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Profile circular avatar
            Surface(
                modifier = Modifier
                    .size(38.dp)
                    .clip(CircleShape)
                    .clickable { onOpenSettings() },
                color = Color(0xFF202020),
                shape = CircleShape,
                border = BorderStroke(1.dp, Color(0xFF2E2E2E))
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = "Settings",
                        tint = Color(0xFFA1A1AA),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            // Center Pill Mode Switch: [ 🔍 Search ] | [ 💻 Assistant ]
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF1C1C1C),
                border = BorderStroke(1.dp, Color(0xFF282828))
            ) {
                Row(
                    modifier = Modifier.padding(3.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Search mode icon
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(16.dp))
                            .background(if (selectedTopMode == 0) Color(0xFF2A2A2A) else Color.Transparent)
                            .clickable { selectedTopMode = 0 }
                            .padding(horizontal = 16.dp, vertical = 6.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = "Search",
                            tint = if (selectedTopMode == 0) TextPrimary else TextMuted,
                            modifier = Modifier.size(16.dp)
                        )
                    }

                    // Computer / Assistant mode icon
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(16.dp))
                            .background(if (selectedTopMode == 1) Color(0xFF2A2A2A) else Color.Transparent)
                            .clickable { selectedTopMode = 1 }
                            .padding(horizontal = 16.dp, vertical = 6.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Laptop,
                            contentDescription = "Computer Assistant",
                            tint = if (selectedTopMode == 1) TextPrimary else TextMuted,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }

            // Right: Library / Collection button
            Surface(
                modifier = Modifier
                    .size(38.dp)
                    .clip(CircleShape)
                    .clickable { onOpenGuide() },
                color = Color(0xFF202020),
                shape = CircleShape,
                border = BorderStroke(1.dp, Color(0xFF2E2E2E))
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.CollectionsBookmark,
                        contentDescription = "Guide",
                        tint = Color(0xFFA1A1AA),
                        modifier = Modifier.size(17.dp)
                    )
                }
            }
        }

        // ═══ 2. Center Minimalist Space with Brand (Matching Screenshot 1) ═══
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "perplexity",
                color = Color(0xFF71717A),
                fontSize = 28.sp,
                fontWeight = FontWeight.Normal,
                letterSpacing = (-0.5).sp,
                fontFamily = FontFamily.SansSerif
            )
        }

        // ═══ 3. Bottom Section (Matching Screenshot 1) ═══
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Contextual Action Card: "Put Computer to work"
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(18.dp))
                    .clickable {
                        onNavigateToChat("Put Computer to work: ")
                    },
                shape = RoundedCornerShape(18.dp),
                color = Color(0xFF1C1C1C),
                border = BorderStroke(1.dp, Color(0xFF282828))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        Surface(
                            modifier = Modifier.size(36.dp),
                            shape = RoundedCornerShape(10.dp),
                            color = Color(0xFF252525),
                            border = BorderStroke(1.dp, Color(0xFF333333))
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.Laptop,
                                    contentDescription = null,
                                    tint = TextPrimary,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }

                        Spacer(modifier = Modifier.width(12.dp))

                        Column {
                            Text(
                                text = "Put Computer to work",
                                color = TextPrimary,
                                fontSize = 13.5.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "Hand off any project",
                                color = TextSecondary,
                                fontSize = 11.5.sp
                            )
                        }
                    }

                    Surface(
                        modifier = Modifier.size(34.dp),
                        shape = CircleShape,
                        color = Color(0xFF252525)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.ArrowUpward,
                                contentDescription = "Start",
                                tint = TextPrimary,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }
                }
            }

            // Primary Floating Command Capsule (Matching Screenshot 1)
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(22.dp),
                color = Color(0xFF1C1C1C),
                border = BorderStroke(1.dp, Color(0xFF282828))
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                ) {
                    TextField(
                        value = queryText,
                        onValueChange = { queryText = it },
                        placeholder = {
                            Text(
                                text = "Do anything...",
                                color = Color(0xFF71717A),
                                fontSize = 15.sp
                            )
                        },
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = Color.Transparent,
                            unfocusedContainerColor = Color.Transparent,
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary,
                            cursorColor = TextPrimary
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
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Left: Plus button (Screenshot 1)
                        IconButton(
                            onClick = {
                                onNavigateToChat("Analyze current screen context and inspect interface.")
                            },
                            modifier = Modifier.size(36.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Add,
                                contentDescription = "Attach / Tools",
                                tint = TextSecondary,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        // Right: Mode / Mic / Send button
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(
                                onClick = onOpenOverlay,
                                modifier = Modifier.size(36.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Mic,
                                    contentDescription = "Voice Assistant",
                                    tint = TextSecondary,
                                    modifier = Modifier.size(20.dp)
                                )
                            }

                            if (queryText.isNotBlank()) {
                                Spacer(modifier = Modifier.width(4.dp))
                                Box(
                                    modifier = Modifier
                                        .size(34.dp)
                                        .clip(CircleShape)
                                        .background(TextPrimary)
                                        .clickable {
                                            onNavigateToChat(queryText)
                                        },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.ArrowUpward,
                                        contentDescription = "Send",
                                        tint = VoidBlack,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
