package com.assistant.athena.ui

import androidx.compose.animation.Crossfade
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
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

enum class CyberTab(val label: String, val icon: ImageVector) {
    DASHBOARD("Core", Icons.Default.Adjust),
    CHAT("Chat", Icons.Default.Forum),
    NOTES("Vault", Icons.Default.Book),
    MCP("MCP", Icons.Default.Extension),
    SKILLS("Tools", Icons.Default.Psychology),
    SETTINGS("Config", Icons.Default.Tune)
}

@Composable
fun CyberpunkAppShell(
    networkClient: NetworkClient,
    status: BackendStatus,
    onOpenOverlay: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenGuide: () -> Unit,
    onRefreshStatus: () -> Unit,
    dashboardContent: @Composable () -> Unit
) {
    var currentTab by remember { mutableStateOf(CyberTab.DASHBOARD) }

    DotMatrixBackground {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = PanelDarkSolid,
                    border = BorderStroke(1.dp, PanelStroke)
                ) {
                    NavigationBar(
                        containerColor = Color.Transparent,
                        contentColor = NeonCyan,
                        tonalElevation = 0.dp
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
                                        tint = if (isSelected) NeonCyan else TextMuted
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
                        CyberTab.DASHBOARD -> dashboardContent()
                        CyberTab.CHAT -> SessionsChatScreen(
                            networkClient = networkClient,
                            onLaunchOverlay = onOpenOverlay
                        )
                        CyberTab.NOTES -> NotesVaultScreen(
                            networkClient = networkClient
                        )
                        CyberTab.MCP -> McpManagerScreen(
                            networkClient = networkClient
                        )
                        CyberTab.SKILLS -> SkillsToolsScreen(
                            networkClient = networkClient
                        )
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
