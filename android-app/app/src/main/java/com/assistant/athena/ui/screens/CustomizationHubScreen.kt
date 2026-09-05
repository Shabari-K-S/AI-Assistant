package com.assistant.athena.ui.screens

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun CustomizationHubScreen(
    networkClient: NetworkClient,
    onOpenSettings: () -> Unit,
    onOpenGuide: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var baseUrlInput by remember { mutableStateOf(networkClient.baseUrl) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    var isCheckingConnection by remember { mutableStateOf(false) }

    var threshold by remember { mutableFloatStateOf(0.40f) }
    var isMuted by remember { mutableStateOf(false) }
    var shellPolicy by remember { mutableStateOf("ask") }
    var selectedModel by remember { mutableStateOf("gemini-3.5-flash-lite") }

    val models = listOf("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash", "gemma-4-31b-it")
    val policies = listOf("ask", "always", "never")

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ═════ 1. Header ═════
        item {
            Column {
                Text(
                    text = "SETTINGS & TELEMETRY HUB",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    letterSpacing = 1.sp
                )
                Text(
                    text = "Configure neural models, voice sensitivity, and bridge links",
                    color = TextMuted,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        // ═════ 2. Backend Bridge Link Config ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "AI BACKEND BRIDGE URL",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    letterSpacing = 0.8.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = baseUrlInput,
                    onValueChange = { baseUrlInput = it },
                    label = { Text("Base URL (Termux local or LAN IP)", color = TextSecondary) },
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

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            coroutineScope.launch {
                                networkClient.baseUrl = baseUrlInput.trim()
                                isCheckingConnection = true
                                val (online, phase, model) = networkClient.checkHealth()
                                isCheckingConnection = false
                                connectionStatus = if (online) "Connected ($phase) • $model" else "Backend Unreachable"
                                Toast.makeText(context, if (online) "Link verified!" else "Connection failed", Toast.LENGTH_SHORT).show()
                            }
                        },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = VoidBlack)
                    ) {
                        Text(if (isCheckingConnection) "TESTING..." else "APPLY & TEST", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }

                    OutlinedButton(
                        onClick = {
                            baseUrlInput = NetworkClient.DEFAULT_BASE_URL
                            networkClient.baseUrl = NetworkClient.DEFAULT_BASE_URL
                            Toast.makeText(context, "Reset to 127.0.0.1:2027", Toast.LENGTH_SHORT).show()
                        },
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, PanelStroke)
                    ) {
                        Text("RESET", color = TextSecondary, fontSize = 12.sp)
                    }
                }

                if (connectionStatus != null) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = connectionStatus!!,
                        color = if (connectionStatus!!.contains("Connected")) NeonGreen else NeonRed,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        // ═════ 3. Neural Voice & Wake Sensitivity ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "NEURAL VOICE & AUDIO PIPELINE",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    letterSpacing = 0.8.sp
                )

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Wake Word Sensitivity", color = TextPrimary, fontSize = 13.sp)
                    Text(
                        text = String.format("%.2f", threshold),
                        color = NeonCyan,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Slider(
                    value = threshold,
                    onValueChange = { threshold = it },
                    onValueChangeFinished = {
                        coroutineScope.launch {
                            networkClient.updateConfig(threshold = threshold)
                        }
                    },
                    valueRange = 0.10f..0.90f,
                    colors = SliderDefaults.colors(
                        thumbColor = NeonCyan,
                        activeTrackColor = NeonCyan,
                        inactiveTrackColor = DeepNavy
                    )
                )

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("Mute Assistant Audio Output", color = TextPrimary, fontSize = 13.sp)
                        Text("Text-only mode for meetings & quiet environments", color = TextMuted, fontSize = 11.sp)
                    }
                    Switch(
                        checked = isMuted,
                        onCheckedChange = {
                            isMuted = it
                            coroutineScope.launch {
                                networkClient.updateConfig(muted = isMuted)
                            }
                        },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = VoidBlack,
                            checkedTrackColor = NeonCyan
                        )
                    )
                }
            }
        }

        // ═════ 4. Primary Conversational LLM Model ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "PRIMARY LLM BRAIN MODEL",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    letterSpacing = 0.8.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                models.forEach { m ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = selectedModel == m,
                            onClick = { selectedModel = m },
                            colors = RadioButtonDefaults.colors(selectedColor = NeonCyan, unselectedColor = TextMuted)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = m, color = TextHighlight, fontSize = 13.sp)
                    }
                }
            }
        }

        // ═════ 5. Operator Safety & Shell Policies ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "OPERATOR CONFIRMATION GATING",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    letterSpacing = 0.8.sp
                )

                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Policy for system commands and automated shell actions",
                    color = TextMuted,
                    fontSize = 11.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    policies.forEach { p ->
                        FilterChip(
                            selected = shellPolicy == p,
                            onClick = { shellPolicy = p },
                            label = { Text(p.uppercase(), fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = NeonCyan,
                                selectedLabelColor = VoidBlack,
                                containerColor = DeepNavy,
                                labelColor = TextSecondary
                            )
                        )
                    }
                }
            }
        }

        // ═════ 6. Android System Gestures & Access ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "SYSTEM ASSISTANT CONFIG",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    letterSpacing = 0.8.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedButton(
                    onClick = onOpenSettings,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, PanelStroke)
                ) {
                    Icon(Icons.Default.Settings, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("SET AS DEFAULT ANDROID ASSISTANT", color = TextHighlight, fontSize = 12.sp)
                }

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedButton(
                    onClick = onOpenGuide,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, PanelStroke)
                ) {
                    Icon(Icons.Default.TouchApp, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("GESTURES & ACCESS SHORTCUTS GUIDE", color = TextHighlight, fontSize = 12.sp)
                }
            }
        }
    }
}
