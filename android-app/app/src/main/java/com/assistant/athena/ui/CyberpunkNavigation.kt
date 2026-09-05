package com.assistant.athena.ui

import androidx.compose.animation.Crossfade
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.BackendStatus
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.ui.components.DotMatrixBackground
import com.assistant.athena.ui.screens.*
import com.assistant.athena.ui.theme.*

// ═════════════════════════════════════════════════════════════════════════════
// 5 Streamlined Perplexity Mobile Tabs
// ═════════════════════════════════════════════════════════════════════════════
enum class CyberTab(val label: String, val icon: ImageVector) {
    HOME("Home", Icons.Default.Explore),
    CHAT("Chat", Icons.Default.Forum),
    LIBRARY("Library", Icons.Default.Bookmark),
    TOOLS("Tools", Icons.Default.Extension),
    SETTINGS("Settings", Icons.Default.Tune)
}

@Composable
fun CyberpunkAppShell(
    networkClient: NetworkClient,
    status: BackendStatus,
    onOpenOverlay: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenGuide: () -> Unit,
    onRefreshStatus: () -> Unit,
    dashboardContent: @Composable (onNavigateToChat: (String?) -> Unit) -> Unit
) {
    var currentTab by remember { mutableStateOf(CyberTab.HOME) }
    var pendingChatPrompt by remember { mutableStateOf<String?>(null) }
    var toolsSegment by remember { mutableStateOf(0) }

    DotMatrixBackground {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = PanelDarkSolid,
                    shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp),
                    border = BorderStroke(1.dp, PanelStroke.copy(alpha = 0.5f)),
                    shadowElevation = 8.dp
                ) {
                    NavigationBar(
                        containerColor = Color.Transparent,
                        contentColor = NeonCyan,
                        tonalElevation = 0.dp,
                        modifier = Modifier.height(64.dp)
                    ) {
                        CyberTab.values().forEach { tab ->
                            val isSelected = currentTab == tab
                            NavigationBarItem(
                                selected = isSelected,
                                onClick = { currentTab = tab },
                                icon = {
                                    Icon(
                                        imageVector = tab.icon,
                                        contentDescription = tab.label,
                                        tint = if (isSelected) NeonCyan else TextMuted,
                                        modifier = Modifier.size(20.dp)
                                    )
                                },
                                label = {
                                    Text(
                                        text = tab.label,
                                        fontSize = 10.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) NeonCyan else TextMuted
                                    )
                                },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = NeonCyan,
                                    unselectedIconColor = TextMuted,
                                    selectedTextColor = NeonCyan,
                                    unselectedTextColor = TextMuted,
                                    indicatorColor = NeonCyanDim
                                )
                            )
                        }
                    }
                }
            }
        ) { paddingValues ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
            ) {
                Crossfade(targetState = currentTab, label = "ScreenTransition") { tab ->
                    when (tab) {
                        CyberTab.HOME -> dashboardContent { prompt ->
                            if (!prompt.isNullOrBlank()) {
                                pendingChatPrompt = prompt
                            }
                            currentTab = CyberTab.CHAT
                        }
                        CyberTab.CHAT -> SessionsChatScreen(
                            networkClient = networkClient,
                            onLaunchOverlay = onOpenOverlay,
                            initialPrompt = pendingChatPrompt,
                            onPromptConsumed = { pendingChatPrompt = null }
                        )
                        CyberTab.LIBRARY -> NotesVaultScreen(
                            networkClient = networkClient
                        )
                        CyberTab.TOOLS -> {
                            Column(modifier = Modifier.fillMaxSize()) {
                                // Perplexity-style Tools Segment Bar
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    color = PanelDarkSolid,
                                    border = BorderStroke(1.dp, PanelStroke.copy(alpha = 0.4f))
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 16.dp, vertical = 10.dp),
                                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                                    ) {
                                        Surface(
                                            modifier = Modifier
                                                .weight(1f)
                                                .clip(RoundedCornerShape(16.dp))
                                                .clickable { toolsSegment = 0 },
                                            color = if (toolsSegment == 0) NeonCyanDim else Color.Transparent,
                                            border = BorderStroke(1.dp, if (toolsSegment == 0) NeonCyan else PanelStroke),
                                            shape = RoundedCornerShape(16.dp)
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(vertical = 7.dp),
                                                horizontalArrangement = Arrangement.Center,
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Icon(
                                                    Icons.Default.Extension,
                                                    contentDescription = null,
                                                    tint = if (toolsSegment == 0) NeonCyan else TextMuted,
                                                    modifier = Modifier.size(15.dp)
                                                )
                                                Spacer(modifier = Modifier.width(6.dp))
                                                Text(
                                                    "MCP CONNECTORS",
                                                    color = if (toolsSegment == 0) TextPrimary else TextMuted,
                                                    fontSize = 11.sp,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }

                                        Surface(
                                            modifier = Modifier
                                                .weight(1f)
                                                .clip(RoundedCornerShape(16.dp))
                                                .clickable { toolsSegment = 1 },
                                            color = if (toolsSegment == 1) NeonCyanDim else Color.Transparent,
                                            border = BorderStroke(1.dp, if (toolsSegment == 1) NeonCyan else PanelStroke),
                                            shape = RoundedCornerShape(16.dp)
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(vertical = 7.dp),
                                                horizontalArrangement = Arrangement.Center,
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Icon(
                                                    Icons.Default.Psychology,
                                                    contentDescription = null,
                                                    tint = if (toolsSegment == 1) NeonCyan else TextMuted,
                                                    modifier = Modifier.size(15.dp)
                                                )
                                                Spacer(modifier = Modifier.width(6.dp))
                                                Text(
                                                    "AI SKILLS",
                                                    color = if (toolsSegment == 1) TextPrimary else TextMuted,
                                                    fontSize = 11.sp,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }
                                    }
                                }

                                Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                                    if (toolsSegment == 0) {
                                        McpManagerScreen(networkClient = networkClient)
                                    } else {
                                        SkillsToolsScreen(networkClient = networkClient)
                                    }
                                }
                            }
                        }
                        CyberTab.SETTINGS -> CustomizationHubScreen(
                            networkClient = networkClient,
                            onOpenSettings = onOpenSettings,
                            onOpenGuide = onOpenGuide
                        )
                    }
                }
            }
        }
    }
}
