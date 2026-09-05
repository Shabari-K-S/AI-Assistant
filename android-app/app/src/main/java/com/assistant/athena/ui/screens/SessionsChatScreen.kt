package com.assistant.athena.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.data.MessageItem
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.data.SessionDetail
import com.assistant.athena.data.SessionItem
import com.assistant.athena.data.ToolData
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

/**
 * Tactical Holographic Cyberpunk Multi-Session Chat Screen for A.T.H.E.N.A.
 * Implements real-time neural streaming, Markdown code blocks, tool feedback,
 * and optimistic turns via /ask bridge protocol.
 */
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
    var localMessages by remember { mutableStateOf<List<MessageItem>>(emptyList()) }
    var isLoadingSessions by remember { mutableStateOf(false) }
    var isLoadingChat by remember { mutableStateOf(false) }
    var isSending by remember { mutableStateOf(false) }

    var inputText by remember { mutableStateOf("") }
    var isHistoryDrawerOpen by remember { mutableStateOf(false) }

    // Dialog for renaming session
    var sessionToRename by remember { mutableStateOf<SessionItem?>(null) }
    var renameDialogText by remember { mutableStateOf("") }

    // Synchronize local messages with loaded session detail
    LaunchedEffect(activeSessionDetail) {
        activeSessionDetail?.let {
            localMessages = it.messages
            if (localMessages.isNotEmpty()) {
                listState.animateScrollToItem(localMessages.size - 1)
            }
        }
    }

    // Load sessions list
    fun reloadSessions(selectFirst: Boolean = false) {
        coroutineScope.launch {
            isLoadingSessions = true
            val fetched = networkClient.fetchSessions()
            sessions = fetched
            isLoadingSessions = false
            if (selectFirst && fetched.isNotEmpty() && activeSessionId == null) {
                activeSessionId = fetched.first().id
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

    // Handle Send Action
    fun executeSendPrompt() {
        val query = inputText.trim()
        if (query.isBlank() || isSending) return

        inputText = ""
        coroutineScope.launch {
            // 1. Optimistically append user message immediately to the UI
            val tempUserMsg = MessageItem(
                id = UUID.randomUUID().toString(),
                role = "user",
                text = query,
                timestamp = System.currentTimeMillis() / 1000.0
            )
            localMessages = localMessages + tempUserMsg
            isSending = true

            // Auto-scroll to bottom
            if (localMessages.isNotEmpty()) {
                listState.animateScrollToItem(localMessages.size - 1)
            }

            // 2. Transmit via synchronous /ask bridge endpoint
            val result = networkClient.askAssistant(query, activeSessionId)

            if (result != null) {
                // If this was a new conversation, bind to the returned session ID
                if (activeSessionId == null || activeSessionId != result.sessionId) {
                    activeSessionId = result.sessionId
                }

                val replyText = result.reply.ifBlank { "Acknowledged. Task processed." }
                val assistantMsg = MessageItem(
                    id = UUID.randomUUID().toString(),
                    role = "assistant",
                    text = replyText,
                    timestamp = System.currentTimeMillis() / 1000.0
                )
                localMessages = localMessages + assistantMsg

                // Sync with backend DB in background
                reloadSessions()
                result.sessionId.let { reloadActiveSession(it) }
            } else {
                // Transmission Failure Alert
                val errorMsg = MessageItem(
                    id = UUID.randomUUID().toString(),
                    role = "system",
                    text = "⚠️ Transmission link timeout or host unreachable. Verify backend server on :2027.",
                    timestamp = System.currentTimeMillis() / 1000.0
                )
                localMessages = localMessages + errorMsg
            }

            isSending = false
            if (localMessages.isNotEmpty()) {
                listState.animateScrollToItem(localMessages.size - 1)
            }
        }
    }

    // ═════ Rename Session Dialog ═════
    if (sessionToRename != null) {
        AlertDialog(
            onDismissRequest = { sessionToRename = null },
            title = {
                Text(
                    text = "RENAME CONVERSATION",
                    color = NeonCyan,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp
                )
            },
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
                        unfocusedTextColor = TextPrimary,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack
                    ),
                    shape = RoundedCornerShape(8.dp)
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        val target = sessionToRename
                        if (target != null && renameDialogText.isNotBlank()) {
                            coroutineScope.launch {
                                val ok = networkClient.renameSession(target.id, renameDialogText.trim())
                                if (ok) {
                                    reloadSessions()
                                    if (activeSessionId == target.id) {
                                        reloadActiveSession(target.id)
                                    }
                                }
                                sessionToRename = null
                            }
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = NeonCyan)
                ) {
                    Text("SAVE", color = VoidBlack, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { sessionToRename = null }) {
                    Text("CANCEL", color = TextMuted)
                }
            },
            containerColor = PanelDarkSolid,
            shape = RoundedCornerShape(12.dp)
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {

            // ═════════════════════════════════════════════════════════════════
            // 1. Tactical HUD Header Bar
            // ═════════════════════════════════════════════════════════════════
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = PanelDarkSolid,
                border = BorderStroke(1.dp, PanelStroke)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Session History Drawer Trigger Chip
                    Surface(
                        modifier = Modifier
                            .clickable { isHistoryDrawerOpen = true }
                            .clip(RoundedCornerShape(8.dp)),
                        color = NeonCyanDim,
                        border = BorderStroke(1.dp, PanelStrokeActive)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.FolderOpen,
                                contentDescription = "History Drawer",
                                tint = NeonCyan,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "SESSIONS",
                                color = NeonCyan,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace,
                                letterSpacing = 1.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(10.dp))

                    // Active Session Title & Status
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clickable { isHistoryDrawerOpen = true }
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            // Pulsing green/cyan online status dot
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(NeonGreen)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = activeSessionDetail?.title ?: "Select Conversation",
                                color = TextPrimary,
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        Text(
                            text = "${localMessages.size} TURNS // PROTOCOL: SYS.READY",
                            color = TextMuted,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            letterSpacing = 0.8.sp
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    // + New Session Button
                    IconButton(
                        onClick = {
                            coroutineScope.launch {
                                val newSession = networkClient.createSession()
                                if (newSession != null) {
                                    activeSessionId = newSession.id
                                    localMessages = emptyList()
                                    reloadSessions()
                                }
                            }
                        },
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(NeonCyanDim)
                            .border(BorderStroke(1.dp, PanelStroke), RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = "New Session",
                            tint = NeonCyan,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(6.dp))

                    // Floating HUD Overlay Launcher
                    IconButton(
                        onClick = onLaunchOverlay,
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(NeonCyanLight.copy(alpha = 0.15f))
                            .border(BorderStroke(1.dp, NeonCyanLight.copy(alpha = 0.4f)), RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Bolt,
                            contentDescription = "Launch Overlay",
                            tint = NeonCyanLight,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            // ═════════════════════════════════════════════════════════════════
            // 2. Chat Feed Area
            // ═════════════════════════════════════════════════════════════════
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                if (isLoadingChat && localMessages.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = NeonCyan, modifier = Modifier.size(36.dp))
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = "SYNCHRONIZING THOUGHT STREAM...",
                                color = TextMuted,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                } else if (localMessages.isEmpty()) {
                    // Empty Session Slate (Tactical Holographic Intro)
                    CyberEmptyState(
                        onSelectSample = { sample ->
                            inputText = sample
                            executeSendPrompt()
                        }
                    )
                } else {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        items(localMessages, key = { it.id }) { msg ->
                            CyberChatMessageBubble(
                                msg = msg,
                                onCopy = { textToCopy ->
                                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                    cm.setPrimaryClip(ClipData.newPlainText("ATHENA", textToCopy))
                                    Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                                }
                            )
                        }

                        // Animated Quantum Reasoning Bar
                        if (isSending) {
                            item {
                                CyberThinkingIndicator()
                            }
                        }
                    }
                }
            }

            // ═════════════════════════════════════════════════════════════════
            // 3. Tactical Command Deck Input Bar
            // ═════════════════════════════════════════════════════════════════
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = PanelDarkSolid,
                border = BorderStroke(1.dp, PanelStroke)
            ) {
                Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {

                    // Quick Action Chips Row
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState())
                            .padding(bottom = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        CyberQuickChip(text = "⚡ Deep Research", icon = Icons.Default.Search) {
                            inputText = "/research "
                        }
                        CyberQuickChip(text = "🛡️ Recon Scan", icon = Icons.Default.Security) {
                            inputText = "/recon "
                        }
                        CyberQuickChip(text = "☀️ Daily Briefing", icon = Icons.Default.WbSunny) {
                            inputText = "/briefing"
                            executeSendPrompt()
                        }
                        CyberQuickChip(text = "📚 Vault Notes", icon = Icons.Default.Book) {
                            inputText = "List my recent notes in the vault"
                            executeSendPrompt()
                        }
                        CyberQuickChip(text = "❓ /help", icon = Icons.Default.HelpOutline) {
                            inputText = "/help"
                            executeSendPrompt()
                        }
                    }

                    // Input Field & Send Action
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            placeholder = {
                                Text(
                                    text = "Transmit command or /prompt to Athena...",
                                    color = TextMuted,
                                    fontSize = 13.sp
                                )
                            },
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 50.dp, max = 130.dp),
                            shape = RoundedCornerShape(10.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = NeonCyan,
                                unfocusedBorderColor = PanelStroke,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedContainerColor = VoidBlack,
                                unfocusedContainerColor = VoidBlack,
                                cursorColor = NeonCyan
                            ),
                            trailingIcon = {
                                if (inputText.isNotEmpty()) {
                                    IconButton(
                                        onClick = { inputText = "" },
                                        modifier = Modifier.size(24.dp)
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Close,
                                            contentDescription = "Clear",
                                            tint = TextMuted,
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
                                }
                            }
                        )

                        Spacer(modifier = Modifier.width(8.dp))

                        // Glowing Cyan Send Button
                        val sendButtonColor = if (inputText.isNotBlank() && !isSending) NeonCyan else NeonCyanDim
                        IconButton(
                            onClick = { executeSendPrompt() },
                            modifier = Modifier
                                .size(48.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(sendButtonColor)
                                .border(BorderStroke(1.dp, if (inputText.isNotBlank()) NeonCyan else PanelStroke), RoundedCornerShape(10.dp)),
                            enabled = !isSending && inputText.isNotBlank()
                        ) {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "Transmit",
                                tint = if (inputText.isNotBlank() && !isSending) VoidBlack else TextMuted,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }
            }
        }

        // ═════════════════════════════════════════════════════════════════
        // 4. History Sessions Modal Bottom Sheet
        // ═════════════════════════════════════════════════════════════════
        if (isHistoryDrawerOpen) {
            ModalBottomSheet(
                onDismissRequest = { isHistoryDrawerOpen = false },
                containerColor = DeepNavy,
                scrimColor = Color.Black.copy(alpha = 0.75f),
                shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
                dragHandle = {
                    Box(
                        modifier = Modifier
                            .padding(vertical = 10.dp)
                            .size(width = 40.dp, height = 4.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(NeonCyanDim)
                    )
                }
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .fillMaxHeight(0.85f)
                        .padding(horizontal = 18.dp, vertical = 6.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "CONVERSATION THREAD VAULT",
                                color = NeonCyan,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.2.sp,
                                fontSize = 15.sp,
                                fontFamily = FontFamily.Monospace
                            )
                            Text(
                                text = "${sessions.size} ARCHIVED SESSIONS",
                                color = TextMuted,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }

                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    val newS = networkClient.createSession()
                                    if (newS != null) {
                                        activeSessionId = newS.id
                                        localMessages = emptyList()
                                        reloadSessions()
                                        isHistoryDrawerOpen = false
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = NeonCyan),
                            shape = RoundedCornerShape(8.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, tint = VoidBlack, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("NEW CHAT", color = VoidBlack, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    if (sessions.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(
                                text = "No conversation threads recorded in vault",
                                color = TextMuted,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp
                            )
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(sessions, key = { it.id }) { s ->
                                CyberSessionHistoryItemRow(
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
                                                    localMessages = emptyList()
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

// ═════════════════════════════════════════════════════════════════════════════
// Tactical Sci-Fi Chat Message Bubble with Markdown Rendering
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberChatMessageBubble(msg: MessageItem, onCopy: (String) -> Unit) {
    val isUser = msg.role == "user"
    val isSystem = msg.role == "system"

    val timeStr = remember(msg.timestamp) {
        val date = Date((msg.timestamp * 1000).toLong())
        SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(date)
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        // Tool execution pill
        if (msg.toolData != null) {
            Surface(
                color = PanelDarkSolid,
                shape = RoundedCornerShape(6.dp),
                border = BorderStroke(1.dp, NeonAmber.copy(alpha = 0.6f)),
                modifier = Modifier.padding(bottom = 6.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "⚡", fontSize = 11.sp)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "EXECUTED: ${msg.toolData.name} (${msg.toolData.durationMs.toInt()}ms)",
                        color = NeonAmber,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        // Main Bubble Container
        Surface(
            color = when {
                isSystem -> NeonRed.copy(alpha = 0.12f)
                isUser -> NeonCyanDim
                else -> PanelDarkSolid
            },
            shape = RoundedCornerShape(
                topStart = if (isUser) 14.dp else 2.dp,
                topEnd = 14.dp,
                bottomStart = 14.dp,
                bottomEnd = if (isUser) 2.dp else 14.dp
            ),
            border = BorderStroke(
                1.dp,
                when {
                    isSystem -> NeonRed.copy(alpha = 0.5f)
                    isUser -> PanelStrokeActive
                    else -> PanelStroke
                }
            ),
            modifier = Modifier.fillMaxWidth(if (isSystem) 1f else 0.88f)
        ) {
            Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {

                // Role Header & Action Row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = when {
                                isSystem -> "SYSTEM NOTICE"
                                isUser -> "[OPERATOR // UPLINK]"
                                else -> "[A.T.H.E.N.A. // CORE]"
                            },
                            color = when {
                                isSystem -> NeonRed
                                isUser -> NeonCyan
                                else -> NeonGreen
                            },
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = timeStr,
                            color = TextMuted,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    if (!isUser) {
                        IconButton(
                            onClick = { onCopy(msg.text) },
                            modifier = Modifier.size(22.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = "Copy message",
                                tint = TextMuted,
                                modifier = Modifier.size(13.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // Rich Markdown Body Parser
                CyberMarkdownText(text = msg.text, onCopyCode = onCopy)
            }
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// In-Bubble Markdown Text Renderer (Code Blocks, Inline Code, Bolds, Lists)
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberMarkdownText(text: String, onCopyCode: (String) -> Unit) {
    val blocks = remember(text) { parseMarkdownBlocks(text) }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        blocks.forEach { block ->
            when (block) {
                is MarkdownBlock.CodeBlock -> {
                    // Terminal Code Card
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        color = VoidBlack,
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, PanelStroke)
                    ) {
                        Column {
                            // Header bar with language & copy button
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(PanelDarkSolid)
                                    .padding(horizontal = 10.dp, vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = block.language.ifBlank { "CODE" }.uppercase(),
                                    color = NeonCyan,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )

                                Row(
                                    modifier = Modifier
                                        .clickable { onCopyCode(block.code) }
                                        .padding(4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.ContentCopy,
                                        contentDescription = "Copy code",
                                        tint = TextMuted,
                                        modifier = Modifier.size(12.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = "COPY",
                                        color = TextMuted,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }

                            // Code content
                            Text(
                                text = block.code,
                                color = NeonCyanLight,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                lineHeight = 17.sp,
                                modifier = Modifier.padding(10.dp)
                            )
                        }
                    }
                }
                is MarkdownBlock.Paragraph -> {
                    val annotatedString = remember(block.content) {
                        formatInlineMarkdown(block.content)
                    }
                    Text(
                        text = annotatedString,
                        color = TextPrimary,
                        fontSize = 13.5.sp,
                        lineHeight = 20.sp
                    )
                }
            }
        }
    }
}

sealed class MarkdownBlock {
    data class Paragraph(val content: String) : MarkdownBlock()
    data class CodeBlock(val language: String, val code: String) : MarkdownBlock()
}

fun parseMarkdownBlocks(rawText: String): List<MarkdownBlock> {
    val result = mutableListOf<MarkdownBlock>()
    val lines = rawText.lines()
    var inCodeBlock = false
    var codeLang = ""
    val currentCodeLines = mutableListOf<String>()
    val currentParaLines = mutableListOf<String>()

    fun flushParagraph() {
        if (currentParaLines.isNotEmpty()) {
            val content = currentParaLines.joinToString("\n").trim()
            if (content.isNotEmpty()) {
                result.add(MarkdownBlock.Paragraph(content))
            }
            currentParaLines.clear()
        }
    }

    for (line in lines) {
        if (line.trimStart().startsWith("```")) {
            if (inCodeBlock) {
                // End code block
                result.add(MarkdownBlock.CodeBlock(codeLang, currentCodeLines.joinToString("\n")))
                currentCodeLines.clear()
                codeLang = ""
                inCodeBlock = false
            } else {
                // Start code block
                flushParagraph()
                inCodeBlock = true
                codeLang = line.trimStart().removePrefix("```").trim()
            }
        } else if (inCodeBlock) {
            currentCodeLines.add(line)
        } else {
            currentParaLines.add(line)
        }
    }

    if (inCodeBlock && currentCodeLines.isNotEmpty()) {
        result.add(MarkdownBlock.CodeBlock(codeLang, currentCodeLines.joinToString("\n")))
    } else {
        flushParagraph()
    }

    return result
}

fun formatInlineMarkdown(text: String): androidx.compose.ui.text.AnnotatedString {
    return buildAnnotatedString {
        var cursor = 0
        // Match bold **text** or inline code `code`
        val regex = Regex("(\\*(.*?)\\*|`([^`]+)`)")
        val matches = regex.findAll(text)

        for (match in matches) {
            val range = match.range
            if (range.first > cursor) {
                append(text.substring(cursor, range.first))
            }

            val matchedValue = match.value
            if (matchedValue.startsWith("**") && matchedValue.endsWith("**")) {
                val boldContent = matchedValue.removePrefix("**").removeSuffix("**")
                withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = TextPrimary)) {
                    append(boldContent)
                }
            } else if (matchedValue.startsWith("`") && matchedValue.endsWith("`")) {
                val codeContent = matchedValue.removePrefix("`").removeSuffix("`")
                withStyle(
                    SpanStyle(
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan,
                        background = NeonCyanDim
                    )
                ) {
                    append(" $codeContent ")
                }
            } else {
                append(matchedValue)
            }
            cursor = range.last + 1
        }

        if (cursor < text.length) {
            append(text.substring(cursor))
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Animated Cyberpunk Quantum Reasoning Bar
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberThinkingIndicator() {
    val infiniteTransition = rememberInfiniteTransition(label = "PulseTransition")
    val alphaAnim by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AlphaPulse"
    )

    Surface(
        color = PanelDarkSolid,
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, NeonCyan.copy(alpha = alphaAnim)),
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            CircularProgressIndicator(
                color = NeonCyan,
                modifier = Modifier.size(16.dp),
                strokeWidth = 2.dp
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = "ATHENA IS REASONING // DISPATCHING NEURAL TOOLS...",
                color = NeonCyan.copy(alpha = alphaAnim),
                fontSize = 11.5.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 0.8.sp
            )
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Empty State Slate (Tactical Holographic Intro)
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberEmptyState(onSelectSample: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Surface(
            modifier = Modifier.size(72.dp),
            shape = CircleShape,
            color = NeonCyanDim,
            border = BorderStroke(1.5.dp, PanelStrokeActive)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    imageVector = Icons.Default.Forum,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(36.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        Text(
            text = "[A.T.H.E.N.A. // NEURAL CHAT UPLINK]",
            color = NeonCyan,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.4.sp,
            fontSize = 14.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = "Ask questions, dispatch academic deep research, execute MCP tools, or inspect security scopes.",
            color = TextSecondary,
            fontSize = 12.sp,
            textAlign = TextAlign.Center,
            lineHeight = 18.sp,
            modifier = Modifier.padding(horizontal = 16.dp)
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Sample Starters
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SampleStarterChip("⚡ Run deep research on Quantum Computing 2026") {
                onSelectSample("/research Quantum Computing 2026 breakthroughs")
            }
            SampleStarterChip("🛡️ Run automated DAST security reconnaissance on localhost") {
                onSelectSample("/recon 127.0.0.1")
            }
            SampleStarterChip("☀️ Synthesize my morning executive briefing") {
                onSelectSample("/briefing")
            }
        }
    }
}

@Composable
fun SampleStarterChip(label: String, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = PanelDarkSolid,
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, PanelStroke)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Terminal, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(14.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text(text = label, color = TextHighlight, fontSize = 11.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// History Row Item
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberSessionHistoryItemRow(
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
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, if (isActive) NeonCyan else PanelStroke)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (session.isPinned) Icons.Default.PushPin else Icons.Default.Forum,
                contentDescription = null,
                tint = if (session.isPinned) NeonAmber else if (isActive) NeonCyan else TextMuted,
                modifier = Modifier.size(18.dp)
            )

            Spacer(modifier = Modifier.width(10.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = session.title,
                        color = if (isActive) NeonCyan else TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false)
                    )
                    if (session.isPinned) {
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "[PINNED]",
                            color = NeonAmber,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }

                Text(
                    text = if (session.lastMessage.isNotBlank()) session.lastMessage else "No messages recorded",
                    color = TextMuted,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
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
fun CyberQuickChip(text: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.clickable(onClick = onClick),
        color = DeepNavy,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PanelStroke)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(12.dp))
            Spacer(modifier = Modifier.width(6.dp))
            Text(text = text, color = TextHighlight, fontSize = 11.5.sp, fontWeight = FontWeight.Medium)
        }
    }
}
