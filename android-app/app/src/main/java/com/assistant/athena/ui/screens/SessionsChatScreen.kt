package com.assistant.athena.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.assistant.athena.data.MessageItem
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.data.SessionDetail
import com.assistant.athena.data.SessionItem
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionsChatScreen(
    networkClient: NetworkClient,
    onLaunchOverlay: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val listState = rememberLazyListState()

    var sessions by remember { mutableStateOf<List<SessionItem>>(emptyList()) }
    var activeSessionId by remember { mutableStateOf<String?>(null) }
    var activeSessionDetail by remember { mutableStateOf<SessionDetail?>(null) }
    var isLoadingSessions by remember { mutableStateOf(false) }
    var isLoadingChat by remember { mutableStateOf(false) }
    var isSending by remember { mutableStateOf(false) }

    var inputText by remember { mutableStateOf("") }
    var isHistoryDrawerOpen by remember { mutableStateOf(false) }

    // Dialog for renaming session
    var sessionToRename by remember { mutableStateOf<SessionItem?>(null) }
    var renameDialogText by remember { mutableStateOf("") }

    // Load sessions list
    fun reloadSessions(selectFirst: Boolean = false) {
        coroutineScope.launch {
            isLoadingSessions = true
            sessions = networkClient.fetchSessions()
            isLoadingSessions = false
            if (selectFirst && sessions.isNotEmpty() && activeSessionId == null) {
                activeSessionId = sessions.first().id
            }
        }
    }

    // Load active session messages
    fun reloadActiveSession(sid: String) {
        coroutineScope.launch {
            isLoadingChat = true
            val detail = networkClient.fetchSessionDetail(sid)
            activeSessionDetail = detail
            isLoadingChat = false
            if (detail != null && detail.messages.isNotEmpty()) {
                listState.animateScrollToItem(detail.messages.size - 1)
            }
        }
    }

    LaunchedEffect(Unit) {
        reloadSessions(selectFirst = true)
    }

    LaunchedEffect(activeSessionId) {
        activeSessionId?.let { reloadActiveSession(it) }
    }

    // Rename dialog
    if (sessionToRename != null) {
        AlertDialog(
            onDismissRequest = { sessionToRename = null },
            title = { Text("Rename Conversation", color = NeonCyan, fontWeight = FontWeight.Bold) },
            text = {
                OutlinedTextField(
                    value = renameDialogText,
                    onValueChange = { renameDialogText = it },
                    label = { Text("Session Title", color = TextSecondary) },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val target = sessionToRename
                        if (target != null && renameDialogText.isNotBlank()) {
                            coroutineScope.launch {
                                val ok = networkClient.renameSession(target.id, renameDialogText.trim())
                                if (ok) {
                                    reloadSessions()
                                    if (activeSessionId == target.id) {
                                        activeSessionId?.let { reloadActiveSession(it) }
                                    }
                                }
                                sessionToRename = null
                            }
                        }
                    }
                ) {
                    Text("SAVE", color = NeonCyan, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { sessionToRename = null }) {
                    Text("CANCEL", color = TextSecondary)
                }
            },
            containerColor = DeepNavy
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            // ═════ 1. Top Cyberpunk Session Header ═════
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = PanelDarkSolid,
                border = BorderStroke(1.dp, PanelStroke)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = { isHistoryDrawerOpen = true },
                        modifier = Modifier.size(40.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Menu,
                            contentDescription = "Session History Drawer",
                            tint = NeonCyan
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = activeSessionDetail?.title ?: "Select Conversation",
                            color = TextPrimary,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = "${activeSessionDetail?.messages?.size ?: 0} turns // Neural Synced",
                            color = TextMuted,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    // + New Chat button
                    IconButton(
                        onClick = {
                            coroutineScope.launch {
                                val newSession = networkClient.createSession()
                                if (newSession != null) {
                                    activeSessionId = newSession.id
                                    reloadSessions()
                                }
                            }
                        },
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(NeonCyanDim)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = "New Session",
                            tint = NeonCyan
                        )
                    }

                    Spacer(modifier = Modifier.width(6.dp))

                    // Floating HUD Launcher
                    IconButton(
                        onClick = onLaunchOverlay,
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(NeonCyanLight.copy(alpha = 0.15f))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Bolt,
                            contentDescription = "Launch Overlay",
                            tint = NeonCyanLight
                        )
                    }
                }
            }

            // ═════ 2. Chat Feed (LazyColumn) ═════
            Box(modifier = Modifier.weight(1f)) {
                if (isLoadingChat) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = NeonCyan, modifier = Modifier.size(36.dp))
                    }
                } else if (activeSessionDetail?.messages.isNullOrEmpty()) {
                    // Empty Session Slate
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(32.dp),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            imageVector = Icons.Default.Forum,
                            contentDescription = null,
                            tint = NeonCyan.copy(alpha = 0.4f),
                            modifier = Modifier.size(64.dp)
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "INITIALIZE THOUGHT STREAM",
                            color = NeonCyan,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.2.sp,
                            fontSize = 14.sp
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "Ask questions, dispatch research, edit notes, or invoke MCP tools.",
                            color = TextSecondary,
                            fontSize = 12.sp,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                } else {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 14.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(activeSessionDetail?.messages ?: emptyList(), key = { it.id }) { msg ->
                            ChatMessageBubble(msg = msg, onCopy = {
                                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                cm.setPrimaryClip(ClipData.newPlainText("ATHENA", it))
                                Toast.makeText(context, "Copied response", Toast.LENGTH_SHORT).show()
                            })
                        }

                        if (isSending) {
                            item {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 8.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    CircularProgressIndicator(
                                        color = NeonCyan,
                                        modifier = Modifier.size(16.dp),
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(modifier = Modifier.width(10.dp))
                                    Text(
                                        text = "ATHENA is thinking & executing tools...",
                                        color = NeonCyan,
                                        fontSize = 12.sp,
                                        fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // ═════ 3. Bottom Input Row ═════
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = PanelDarkSolid,
                border = BorderStroke(1.dp, PanelStroke)
            ) {
                Column(modifier = Modifier.padding(10.dp)) {
                    // Quick chips row
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        QuickQueryChip(text = "Deep Research", icon = Icons.Default.Search) {
                            inputText = "/research "
                        }
                        QuickQueryChip(text = "Daily Briefing", icon = Icons.Default.WbSunny) {
                            inputText = "Generate daily morning briefing"
                        }
                        QuickQueryChip(text = "Check Notes", icon = Icons.Default.Book) {
                            inputText = "List my recent notes in the vault"
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            placeholder = { Text("Ask ATHENA anything or enter /command...", color = TextMuted, fontSize = 13.sp) },
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 48.dp, max = 120.dp),
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

                        Spacer(modifier = Modifier.width(8.dp))

                        IconButton(
                            onClick = {
                                val q = inputText.trim()
                                if (q.isNotEmpty()) {
                                    inputText = ""
                                    coroutineScope.launch {
                                        isSending = true
                                        networkClient.sendPrompt(q, activeSessionId)
                                        // Wait a moment then reload session
                                        kotlinx.coroutines.delay(1200)
                                        activeSessionId?.let { reloadActiveSession(it) }
                                        isSending = false
                                    }
                                }
                            },
                            modifier = Modifier
                                .size(46.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .background(NeonCyan),
                            enabled = !isSending
                        ) {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "Send",
                                tint = VoidBlack
                            )
                        }
                    }
                }
            }
        }

        // ═════ 4. History Sessions Modal Bottom Sheet ═════
        if (isHistoryDrawerOpen) {
            ModalBottomSheet(
                onDismissRequest = { isHistoryDrawerOpen = false },
                containerColor = DeepNavy,
                scrimColor = Color.Black.copy(alpha = 0.7f)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .fillMaxHeight(0.85f)
                        .padding(horizontal = 18.dp, vertical = 8.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "CONVERSATION HISTORY",
                            color = NeonCyan,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.2.sp,
                            fontSize = 15.sp
                        )

                        TextButton(
                            onClick = {
                                coroutineScope.launch {
                                    val newS = networkClient.createSession()
                                    if (newS != null) {
                                        activeSessionId = newS.id
                                        reloadSessions()
                                        isHistoryDrawerOpen = false
                                    }
                                }
                            }
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("NEW CHAT", color = NeonCyan, fontWeight = FontWeight.Bold)
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    if (sessions.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("No saved conversation threads", color = TextMuted)
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            items(sessions, key = { it.id }) { s ->
                                SessionHistoryItemRow(
                                    session = s,
                                    isActive = s.id == activeSessionId,
                                    onSelect = {
                                        activeSessionId = s.id
                                        isHistoryDrawerOpen = false
                                    },
                                    onRename = {
                                        renameDialogText = s.title
                                        sessionToRename = s
                                    },
                                    onPin = {
                                        coroutineScope.launch {
                                            networkClient.pinSession(s.id)
                                            reloadSessions()
                                        }
                                    },
                                    onDelete = {
                                        coroutineScope.launch {
                                            val ok = networkClient.deleteSession(s.id)
                                            if (ok) {
                                                if (activeSessionId == s.id) {
                                                    activeSessionId = null
                                                }
                                                reloadSessions(selectFirst = true)
                                            }
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChatMessageBubble(msg: MessageItem, onCopy: (String) -> Unit) {
    val isUser = msg.role == "user"

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        // Tool execution feedback pill
        if (msg.toolData != null) {
            Surface(
                color = PanelDark,
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, NeonAmber.copy(alpha = 0.5f)),
                modifier = Modifier.padding(bottom = 4.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "⚡", fontSize = 11.sp)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "${msg.toolData.name} (${msg.toolData.durationMs.toInt()}ms)",
                        color = NeonAmber,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        Surface(
            color = if (isUser) NeonCyanDim else PanelDarkSolid,
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 2.dp,
                bottomEnd = if (isUser) 2.dp else 16.dp
            ),
            border = BorderStroke(1.dp, if (isUser) PanelStrokeActive else PanelStroke),
            modifier = Modifier.widthIn(max = 320.dp)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    text = if (isUser) "OPERATOR" else "A.T.H.E.N.A.",
                    color = if (isUser) NeonCyan else NeonGreen,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = msg.text,
                    color = TextPrimary,
                    fontSize = 14.sp,
                    lineHeight = 20.sp
                )

                if (!isUser) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        IconButton(
                            onClick = { onCopy(msg.text) },
                            modifier = Modifier.size(24.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = "Copy",
                                tint = TextMuted,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SessionHistoryItemRow(
    session: SessionItem,
    isActive: Boolean,
    onSelect: () -> Unit,
    onRename: () -> Unit,
    onPin: () -> Unit,
    onDelete: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onSelect),
        color = if (isActive) NeonCyanDim else PanelDarkSolid,
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, if (isActive) NeonCyan else PanelStroke)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (session.isPinned) Icons.Default.PushPin else Icons.Default.ChatBubbleOutline,
                contentDescription = null,
                tint = if (session.isPinned) NeonAmber else if (isActive) NeonCyan else TextMuted,
                modifier = Modifier.size(18.dp)
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = session.title,
                    color = if (isActive) NeonCyan else TextPrimary,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (session.lastMessage.isNotEmpty()) {
                    Text(
                        text = session.lastMessage,
                        color = TextMuted,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            IconButton(onClick = onRename, modifier = Modifier.size(28.dp)) {
                Icon(Icons.Default.Edit, contentDescription = "Rename", tint = TextMuted, modifier = Modifier.size(14.dp))
            }

            IconButton(onClick = onPin, modifier = Modifier.size(28.dp)) {
                Icon(Icons.Default.PushPin, contentDescription = "Pin", tint = if (session.isPinned) NeonAmber else TextMuted, modifier = Modifier.size(14.dp))
            }

            IconButton(onClick = onDelete, modifier = Modifier.size(28.dp)) {
                Icon(Icons.Default.Delete, contentDescription = "Delete", tint = NeonRed.copy(alpha = 0.7f), modifier = Modifier.size(14.dp))
            }
        }
    }
}

@Composable
fun QuickQueryChip(text: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.clickable(onClick = onClick),
        color = DeepNavy,
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, PanelStroke)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(12.dp))
            Spacer(modifier = Modifier.width(5.dp))
            Text(text = text, color = TextHighlight, fontSize = 11.sp)
        }
    }
}
