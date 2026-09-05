package com.assistant.athena.ui.screens

import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.data.McpCatalogItem
import com.assistant.athena.data.McpServerConfig
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun McpManagerScreen(
    networkClient: NetworkClient
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var servers by remember { mutableStateOf<List<McpServerConfig>>(emptyList()) }
    var catalog by remember { mutableStateOf<List<McpCatalogItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var activeTab by remember { mutableStateOf(0) } // 0: Installed, 1: Catalog & Discovery

    // Expanded servers map
    var expandedServers by remember { mutableStateOf<Map<String, Boolean>>(emptyMap()) }

    // Add server modal
    var showAddDialog by remember { mutableStateOf(false) }
    var addName by remember { mutableStateOf("") }
    var addCommand by remember { mutableStateOf(".venv/bin/python3") }
    var addArgs by remember { mutableStateOf("") }
    var addEnv by remember { mutableStateOf("") }

    // Ecosystem search query
    var discoveryQuery by remember { mutableStateOf("") }
    var discoveryLoading by remember { mutableStateOf(false) }

    fun reloadMcp() {
        coroutineScope.launch {
            isLoading = true
            val (s, c) = networkClient.fetchMcpStatus()
            servers = s
            catalog = c
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        reloadMcp()
    }

    // Add Server Sheet
    if (showAddDialog) {
        ModalBottomSheet(
            onDismissRequest = { showAddDialog = false },
            containerColor = DeepNavy,
            scrimColor = Color.Black.copy(alpha = 0.7f)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = "REGISTER NEW MCP SERVER",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    letterSpacing = 1.sp
                )

                Spacer(modifier = Modifier.height(14.dp))

                OutlinedTextField(
                    value = addName,
                    onValueChange = { addName = it },
                    label = { Text("Server Identifier (e.g. custom-tools)", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = addCommand,
                    onValueChange = { addCommand = it },
                    label = { Text("Executable Command (e.g. npx or python3)", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = addArgs,
                    onValueChange = { addArgs = it },
                    label = { Text("Arguments (comma separated)", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = addEnv,
                    onValueChange = { addEnv = it },
                    label = { Text("Environment (KEY=VAL, comma separated)", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(18.dp))

                Button(
                    onClick = {
                        val name = addName.trim()
                        if (name.isNotEmpty()) {
                            val argsList = addArgs.split(",").map { it.trim() }.filter { it.isNotEmpty() }
                            val envMap = mutableMapOf<String, String>()
                            addEnv.split(",").forEach { pair ->
                                val parts = pair.split("=", limit = 2)
                                if (parts.size == 2) envMap[parts[0].trim()] = parts[1].trim()
                            }
                            coroutineScope.launch {
                                val ok = networkClient.saveMcpServer(name, addCommand.trim(), argsList, envMap)
                                if (ok) {
                                    showAddDialog = false
                                    reloadMcp()
                                    Toast.makeText(context, "Server registered successfully", Toast.LENGTH_SHORT).show()
                                }
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = VoidBlack)
                ) {
                    Text("REGISTER SERVER", fontWeight = FontWeight.Bold)
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // ═════ Top Bar ═════
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = PanelDarkSolid,
            border = BorderStroke(1.dp, PanelStroke)
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "MODEL CONTEXT PROTOCOL (MCP)",
                            color = NeonCyan,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            letterSpacing = 1.sp
                        )
                        val totalTools = servers.sumOf { it.toolsCount }
                        val activeCount = servers.count { it.running }
                        Text(
                            text = "$activeCount active servers // $totalTools registered tools",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    Row {
                        IconButton(onClick = { reloadMcp() }, modifier = Modifier.size(36.dp)) {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = NeonCyan)
                        }

                        IconButton(
                            onClick = {
                                addName = ""
                                addCommand = ".venv/bin/python3"
                                addArgs = ""
                                addEnv = ""
                                showAddDialog = true
                            },
                            modifier = Modifier
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(NeonCyanDim)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = "Add Server", tint = NeonCyan)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                TabRow(
                    selectedTabIndex = activeTab,
                    containerColor = DeepNavy,
                    contentColor = NeonCyan,
                    divider = {}
                ) {
                    Tab(
                        selected = activeTab == 0,
                        onClick = { activeTab = 0 },
                        text = { Text("INSTALLED (${servers.size})", fontWeight = FontWeight.Bold, fontSize = 12.sp) }
                    )
                    Tab(
                        selected = activeTab == 1,
                        onClick = { activeTab = 1 },
                        text = { Text("CATALOG & DISCOVERY", fontWeight = FontWeight.Bold, fontSize = 12.sp) }
                    )
                }
            }
        }

        // ═════ Tab Content ═════
        Box(modifier = Modifier.weight(1f)) {
            if (isLoading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = NeonCyan)
                }
            } else if (activeTab == 0) {
                // Installed Servers List
                if (servers.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("No MCP servers configured", color = TextMuted)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(servers, key = { it.name }) { server ->
                            val isExpanded = expandedServers[server.name] == true
                            McpServerCard(
                                server = server,
                                isExpanded = isExpanded,
                                onToggleExpand = {
                                    expandedServers = expandedServers.toMutableMap().apply {
                                        put(server.name, !isExpanded)
                                    }
                                },
                                onToggleEnabled = { enabled ->
                                    coroutineScope.launch {
                                        val ok = networkClient.toggleMcpServer(server.name, enabled)
                                        if (ok) reloadMcp()
                                    }
                                },
                                onRestart = {
                                    coroutineScope.launch {
                                        val ok = networkClient.restartMcpServer(server.name)
                                        if (ok) {
                                            reloadMcp()
                                            Toast.makeText(context, "${server.name} restarted", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                },
                                onDelete = {
                                    coroutineScope.launch {
                                        val ok = networkClient.deleteMcpServer(server.name)
                                        if (ok) reloadMcp()
                                    }
                                }
                            )
                        }
                    }
                }
            } else {
                // Catalog & Discovery Tab
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        OutlinedTextField(
                            value = discoveryQuery,
                            onValueChange = { discoveryQuery = it },
                            placeholder = { Text("Search MCP ecosystem for tools...", color = TextMuted, fontSize = 13.sp) },
                            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = NeonCyan) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = NeonCyan,
                                unfocusedBorderColor = PanelStroke,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedContainerColor = DeepNavy,
                                unfocusedContainerColor = DeepNavy
                            )
                        )
                    }

                    item {
                        Text(
                            text = "PRE-INSTALLED MCP BUNDLE",
                            color = NeonCyan,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp
                        )
                    }

                    items(catalog, key = { it.id }) { catItem ->
                        val isInstalled = servers.any { it.name == catItem.name || it.name == catItem.id }
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            color = PerplexitySurfaceElevated,
                            shape = RoundedCornerShape(14.dp),
                            border = BorderStroke(1.dp, PerplexityPillBorder)
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Extension,
                                    contentDescription = null,
                                    tint = NeonCyan,
                                    modifier = Modifier.size(24.dp)
                                )

                                Spacer(modifier = Modifier.width(12.dp))

                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = catItem.name,
                                        color = TextPrimary,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = catItem.description,
                                        color = TextSecondary,
                                        fontSize = 12.sp,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }

                                Spacer(modifier = Modifier.width(8.dp))

                                if (isInstalled) {
                                    Surface(
                                        color = NeonGreen.copy(alpha = 0.15f),
                                        shape = RoundedCornerShape(6.dp),
                                        border = BorderStroke(1.dp, NeonGreen.copy(alpha = 0.4f))
                                    ) {
                                        Text(
                                            text = "INSTALLED",
                                            color = NeonGreen,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp)
                                        )
                                    }
                                } else {
                                    Button(
                                        onClick = {
                                            coroutineScope.launch {
                                                val ok = networkClient.saveMcpServer(
                                                    catItem.name,
                                                    catItem.command,
                                                    catItem.args,
                                                    emptyMap()
                                                )
                                                if (ok) {
                                                    reloadMcp()
                                                    Toast.makeText(context, "Installed ${catItem.name}", Toast.LENGTH_SHORT).show()
                                                }
                                            }
                                        },
                                        shape = RoundedCornerShape(8.dp),
                                        colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = VoidBlack),
                                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                                    ) {
                                        Text("INSTALL", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun McpServerCard(
    server: McpServerConfig,
    isExpanded: Boolean,
    onToggleExpand: () -> Unit,
    onToggleEnabled: (Boolean) -> Unit,
    onRestart: () -> Unit,
    onDelete: () -> Unit
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, if (server.running) PerplexityTeal.copy(alpha = 0.5f) else PerplexityPillBorder)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(if (server.running) NeonGreen else NeonRed)
                )

                Spacer(modifier = Modifier.width(10.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = server.name,
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                    Text(
                        text = "${server.toolsCount} tools // ${if (server.running) "online" else "inactive"}",
                        color = if (server.running) NeonGreen else TextMuted,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }

                // Enabled switch
                Switch(
                    checked = server.enabled,
                    onCheckedChange = onToggleEnabled,
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = VoidBlack,
                        checkedTrackColor = NeonCyan,
                        uncheckedTrackColor = DeepNavy
                    )
                )

                IconButton(onClick = onRestart, modifier = Modifier.size(32.dp)) {
                    Icon(Icons.Default.RestartAlt, contentDescription = "Restart", tint = NeonCyan, modifier = Modifier.size(16.dp))
                }

                IconButton(onClick = onDelete, modifier = Modifier.size(32.dp)) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete", tint = NeonRed.copy(alpha = 0.6f), modifier = Modifier.size(16.dp))
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Expandable Tools Toggle Row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggleExpand)
                    .padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "INSPECT REGISTERED TOOLS (${server.tools.size})",
                    color = NeonCyan,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp
                )

                Icon(
                    imageVector = if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
            }

            AnimatedVisibility(visible = isExpanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    server.tools.forEach { tool ->
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            color = DeepNavy,
                            shape = RoundedCornerShape(8.dp),
                            border = BorderStroke(1.dp, PerplexityPillBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Text(
                                    text = "• ${tool.name}",
                                    color = NeonCyan,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                                if (tool.description.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        text = tool.description,
                                        color = TextSecondary,
                                        fontSize = 11.sp,
                                        lineHeight = 15.sp
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
