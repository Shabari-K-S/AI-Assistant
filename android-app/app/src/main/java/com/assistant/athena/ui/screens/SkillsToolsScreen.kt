package com.assistant.athena.ui.screens

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import com.assistant.athena.data.*
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SkillsToolsScreen(
    networkClient: NetworkClient
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var skills by remember { mutableStateOf<List<AthenaSkill>>(emptyList()) }
    var agents by remember { mutableStateOf<List<AthenaAgentProfile>>(emptyList()) }
    var timers by remember { mutableStateOf<List<ActiveTimerItem>>(emptyList()) }
    var briefingData by remember { mutableStateOf<DailyBriefingData?>(null) }
    var isBriefingLoading by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(false) }

    // Dialog for learning skill
    var showLearnDialog by remember { mutableStateOf(false) }
    var learnInput by remember { mutableStateOf("") }

    // Dialog for creating timer
    var showTimerDialog by remember { mutableStateOf(false) }
    var timerDuration by remember { mutableStateOf("25m") }
    var timerLabel by remember { mutableStateOf("Focus Sprint") }

    fun reloadAll() {
        coroutineScope.launch {
            isLoading = true
            skills = networkClient.fetchSkills()
            agents = networkClient.fetchAgents()
            timers = networkClient.fetchTimers()
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        reloadAll()
    }

    // Learn Skill Dialog
    if (showLearnDialog) {
        AlertDialog(
            onDismissRequest = { showLearnDialog = false },
            title = { Text("SYNTHESIZE NEW SKILL", color = NeonCyan, fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text(
                        text = "Enter documentation URL, topic, or rule to ingest into ~/.athena/skills/ via /learn.",
                        color = TextSecondary,
                        fontSize = 12.sp
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                    OutlinedTextField(
                        value = learnInput,
                        onValueChange = { learnInput = it },
                        placeholder = { Text("e.g. https://docs.pwntools.com or GraphQL security", color = TextMuted) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = NeonCyan,
                            unfocusedBorderColor = PanelStroke,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        )
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val input = learnInput.trim()
                        if (input.isNotEmpty()) {
                            coroutineScope.launch {
                                networkClient.sendPrompt("/learn $input")
                                showLearnDialog = false
                                Toast.makeText(context, "Skill synthesis initiated", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                ) {
                    Text("SYNTHESIZE", color = NeonCyan, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLearnDialog = false }) {
                    Text("CANCEL", color = TextSecondary)
                }
            },
            containerColor = DeepNavy
        )
    }

    // Create Timer Dialog
    if (showTimerDialog) {
        AlertDialog(
            onDismissRequest = { showTimerDialog = false },
            title = { Text("NEW SMART TIMER", color = NeonCyan, fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    OutlinedTextField(
                        value = timerDuration,
                        onValueChange = { timerDuration = it },
                        label = { Text("Duration (e.g. 25m, 1h, 300s)", color = TextSecondary) },
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
                        value = timerLabel,
                        onValueChange = { timerLabel = it },
                        label = { Text("Timer Label", color = TextSecondary) },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = NeonCyan,
                            unfocusedBorderColor = PanelStroke,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        )
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        coroutineScope.launch {
                            val ok = networkClient.createTimer(timerDuration.trim(), timerLabel.trim())
                            if (ok) {
                                showTimerDialog = false
                                reloadAll()
                                Toast.makeText(context, "Timer created", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                ) {
                    Text("START", color = NeonCyan, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showTimerDialog = false }) {
                    Text("CANCEL", color = TextSecondary)
                }
            },
            containerColor = DeepNavy
        )
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ═════ 1. Header ═════
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "SKILLS & AUTONOMOUS ENGINES",
                        color = NeonCyan,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = "${skills.size} learned skills // ${agents.size} sub-agents online",
                        color = TextMuted,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }

                IconButton(onClick = { reloadAll() }, modifier = Modifier.size(36.dp)) {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = NeonCyan)
                }
            }
        }

        // ═════ 2. Daily Executive Briefing Section ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.WbSunny, contentDescription = null, tint = NeonAmber, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "DAILY INTELLIGENCE BRIEFING",
                            color = NeonAmber,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp,
                            letterSpacing = 0.8.sp
                        )
                    }

                    Button(
                        onClick = {
                            coroutineScope.launch {
                                isBriefingLoading = true
                                briefingData = networkClient.fetchBriefing("morning")
                                isBriefingLoading = false
                            }
                        },
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = NeonAmber, contentColor = VoidBlack),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                        enabled = !isBriefingLoading
                    ) {
                        Text(if (isBriefingLoading) "GENERATING..." else "GENERATE", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }

                if (briefingData != null) {
                    val b = briefingData!!
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = "${b.city} // ${b.tempC}°C ${b.weatherCondition} • ${b.pendingTodosCount} pending tasks",
                        color = TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = b.spokenSummary,
                        color = TextSecondary,
                        fontSize = 12.sp,
                        lineHeight = 17.sp
                    )
                }
            }
        }

        // ═════ 3. Smart Timers & Pomodoro Focus Section ═════
        item {
            HudCard(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Timer, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "SMART TIMERS & POMODORO",
                            color = NeonCyan,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp,
                            letterSpacing = 0.8.sp
                        )
                    }

                    Row {
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    networkClient.createTimer("25m", "Pomodoro Focus", "pomodoro")
                                    reloadAll()
                                    Toast.makeText(context, "25m Pomodoro started", Toast.LENGTH_SHORT).show()
                                }
                            },
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = NeonCyanDim, contentColor = NeonCyan),
                            border = BorderStroke(1.dp, PanelStroke),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text("25M POMO", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }

                        Spacer(modifier = Modifier.width(6.dp))

                        IconButton(
                            onClick = { showTimerDialog = true },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = "Add", tint = NeonCyan, modifier = Modifier.size(18.dp))
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                if (timers.isEmpty()) {
                    Text("No active countdown timers running", color = TextMuted, fontSize = 12.sp)
                } else {
                    timers.forEach { t ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(text = t.label, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                                Text(text = "${t.remainingSeconds}s remaining", color = NeonCyan, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                                LinearProgressIndicator(
                                    progress = (t.progressPercent / 100.0).toFloat().coerceIn(0f, 1f),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 4.dp),
                                    color = NeonCyan,
                                    trackColor = DeepNavy
                                )
                            }
                            IconButton(
                                onClick = {
                                    coroutineScope.launch {
                                        networkClient.cancelTimer(t.id)
                                        reloadAll()
                                    }
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(Icons.Default.Close, contentDescription = "Cancel", tint = NeonRed, modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }
        }

        // ═════ 4. Learned Skills Library Section ═════
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "LEARNED SKILLS LIBRARY",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    letterSpacing = 0.8.sp
                )

                TextButton(onClick = { showLearnDialog = true }) {
                    Icon(Icons.Default.Add, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("LEARN NEW", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                }
            }
        }

        if (skills.isEmpty()) {
            item {
                Text("No custom skills stored in ~/.athena/skills/", color = TextMuted, fontSize = 12.sp)
            }
        } else {
            items(skills, key = { it.name }) { s ->
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = PanelDarkSolid,
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, PanelStroke)
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Psychology, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(24.dp))
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(text = s.name, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text(text = s.description, color = TextSecondary, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    networkClient.sendPrompt("/skill run ${s.name}")
                                    Toast.makeText(context, "Executing ${s.name}", Toast.LENGTH_SHORT).show()
                                }
                            },
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = NeonCyanDim, contentColor = NeonCyan),
                            border = BorderStroke(1.dp, PanelStroke),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text("RUN", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }

        // ═════ 5. Autonomous Sub-Agents Section ═════
        item {
            Text(
                text = "AUTONOMOUS SUB-AGENTS",
                color = NeonCyan,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp,
                letterSpacing = 0.8.sp
            )
        }

        items(agents, key = { it.name }) { ag ->
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = PanelDarkSolid,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, PanelStroke)
            ) {
                Row(
                    modifier = Modifier.padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.SmartToy, contentDescription = null, tint = NeonGreen, modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = ag.role, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        Text(text = ag.description, color = TextSecondary, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
}
