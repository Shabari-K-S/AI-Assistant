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
import com.assistant.athena.data.ToolExecutionStep
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
    onLaunchOverlay: () -> Unit,
    initialPrompt: String? = null,
    onPromptConsumed: () -> Unit = {}
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

            // 2. Transmit via synchronous /ask bridge endpoint (with screen context if available)
            val isScreenQuery = query.contains("screen", ignoreCase = true)
            val result = if (isScreenQuery && com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()) {
                val imgB64 = com.assistant.athena.data.ScreenCaptureHolder.toBase64Jpeg()
                if (!imgB64.isNullOrEmpty()) {
                    networkClient.askAssistantWithVision(query, imgB64, activeSessionId)
                } else {
                    networkClient.askAssistant(query, activeSessionId)
                }
            } else {
                networkClient.askAssistant(query, activeSessionId)
            }

            if (result != null) {
                // If this was a new conversation, bind to the returned session ID
                if (activeSessionId == null || activeSessionId != result.sessionId) {
                    activeSessionId = result.sessionId
                }

                val replyText = result.reply.ifBlank {
                    if (result.toolData != null) "Task executed successfully." else "Acknowledged. Task processed."
                }
                val assistantMsg = MessageItem(
                    id = UUID.randomUUID().toString(),
                    role = "assistant",
                    text = replyText,
                    timestamp = System.currentTimeMillis() / 1000.0,
                    toolData = result.toolData
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

    // Handle cross-screen prompt handoff (e.g. from Perplexity Home Search)
    LaunchedEffect(initialPrompt) {
        if (!initialPrompt.isNullOrBlank()) {
            inputText = initialPrompt
            onPromptConsumed()
            executeSendPrompt()
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
                color = VoidBlack,
                border = BorderStroke(0.5.dp, Color(0xFF262626))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // History Drawer Trigger
                    IconButton(
                        onClick = { isHistoryDrawerOpen = true },
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Menu,
                            contentDescription = "Conversations",
                            tint = TextSecondary,
                            modifier = Modifier.size(22.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(6.dp))

                    // Active Session Title
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clickable { isHistoryDrawerOpen = true }
                    ) {
                        Text(
                            text = activeSessionDetail?.title ?: "Chat",
                            color = TextPrimary,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 15.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = if (localMessages.isNotEmpty()) "${localMessages.size} messages" else "New thread",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    }

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
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = "New Session",
                            tint = TextSecondary,
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    // Floating Assistant Overlay Launcher
                    IconButton(
                        onClick = onLaunchOverlay,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Bolt,
                            contentDescription = "Assistant HUD",
                            tint = TextSecondary,
                            modifier = Modifier.size(20.dp)
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
                                },
                                onSelectFollowUp = { followUpPrompt ->
                                    inputText = followUpPrompt
                                    executeSendPrompt()
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
            // 3. Perplexity-Style Floating Capsule Command Deck
            // ═════════════════════════════════════════════════════════════════
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(VoidBlack)
                    .padding(horizontal = 14.dp, vertical = 6.dp)
            ) {
                // Focus Mode / Quick Action Chips Row
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(bottom = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CyberQuickChip(
                        text = if (com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()) "📸 Screen Context" else "📸 Ask Screen",
                        icon = Icons.Default.Search
                    ) {
                        if (com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()) {
                            inputText = "Analyze the attached screen context and summarize key insights."
                            executeSendPrompt()
                        } else {
                            inputText = "What's on my screen? (Hold Home/Power button or swipe corner to capture screen)"
                            executeSendPrompt()
                        }
                    }
                    CyberQuickChip(text = "⚡ Pro Research", icon = Icons.Default.Search) {
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

                // Perplexity Floating Pill Input Capsule (Matching Screenshot 1)
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(24.dp),
                    color = Color(0xFF1E1E1E),
                    border = BorderStroke(1.dp, Color(0xFF2B2B2B))
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Left + button (Screenshot 1)
                        IconButton(
                            onClick = {
                                if (com.assistant.athena.data.ScreenCaptureHolder.hasFreshScreenshot()) {
                                    inputText = "Analyze the current screen context."
                                } else {
                                    inputText = "What's on my screen?"
                                }
                                executeSendPrompt()
                            },
                            modifier = Modifier.size(34.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Add,
                                contentDescription = "Attach / Tools",
                                tint = TextSecondary,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        // High-legibility Perplexity Input
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            placeholder = {
                                Text(
                                    text = "Ask anything or follow-up...",
                                    color = Color(0xFF71717A),
                                    fontSize = 14.sp
                                )
                            },
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 42.dp, max = 130.dp),
                            shape = RoundedCornerShape(20.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Color.Transparent,
                                unfocusedBorderColor = Color.Transparent,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedContainerColor = Color.Transparent,
                                unfocusedContainerColor = Color.Transparent,
                                cursorColor = TextPrimary
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

                        Spacer(modifier = Modifier.width(4.dp))

                        // Perplexity Signature Circular Send / Mic Button
                        val isReadyToSend = inputText.isNotBlank() && !isSending
                        if (isReadyToSend) {
                            Box(
                                modifier = Modifier
                                    .size(34.dp)
                                    .clip(CircleShape)
                                    .background(TextPrimary)
                                    .clickable { executeSendPrompt() },
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ArrowUpward,
                                    contentDescription = "Send",
                                    tint = VoidBlack,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        } else {
                            IconButton(
                                onClick = onLaunchOverlay,
                                modifier = Modifier.size(34.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Mic,
                                    contentDescription = "Voice Assistant",
                                    tint = TextSecondary,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
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
fun CyberChatMessageBubble(
    msg: MessageItem,
    onCopy: (String) -> Unit,
    onSelectFollowUp: (String) -> Unit = {}
) {
    val isUser = msg.role == "user"
    val isSystem = msg.role == "system"

    val timeStr = remember(msg.timestamp) {
        val date = Date((msg.timestamp * 1000).toLong())
        SimpleDateFormat("HH:mm", Locale.getDefault()).format(date)
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        if (isUser) {
            // User Message: Clean elevated rounded bubble on the right
            Surface(
                color = Color(0xFF242424),
                shape = RoundedCornerShape(18.dp),
                border = BorderStroke(1.dp, Color(0xFF333333)),
                modifier = Modifier.widthIn(max = 300.dp)
            ) {
                Text(
                    text = msg.text,
                    color = TextPrimary,
                    fontSize = 14.5.sp,
                    lineHeight = 21.sp,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)
                )
            }
        } else {
            // Assistant Message: Natural layout directly on the canvas without heavy box borders
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 4.dp)
            ) {
                // Subtle Header: Athena spark + time + copy action
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "✳",
                            color = PerplexityTeal,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (isSystem) "System" else "Athena",
                            color = TextPrimary,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = timeStr,
                            color = TextMuted,
                            fontSize = 10.sp
                        )
                    }

                    IconButton(
                        onClick = { onCopy(msg.text) },
                        modifier = Modifier.size(28.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = "Copy message",
                            tint = TextMuted,
                            modifier = Modifier.size(15.dp)
                        )
                    }
                }

                // Sources & Citations Carousel
                if (msg.toolData != null && msg.toolData.steps.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    PerplexitySourcesRow(steps = msg.toolData.steps)
                    CyberToolChainAccordion(toolData = msg.toolData, onCopy = onCopy)
                }

                // Rich Markdown Body
                if (msg.text.isNotBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    CyberMarkdownText(text = msg.text, onCopyCode = onCopy)
                }

                // Perplexity Interactive Follow-Up Prompts Section
                if (msg.text.isNotBlank() && !isSystem) {
                    Spacer(modifier = Modifier.height(8.dp))
                    PerplexityFollowUpSection(onSelectPrompt = onSelectFollowUp)
                }
            }
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Perplexity Sources & Citations Carousel
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun PerplexitySourcesRow(steps: List<ToolExecutionStep>) {
    Column(modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Sources",
                color = TextSecondary,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.width(6.dp))
            Surface(
                color = Color(0xFF202020),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, Color(0xFF2E2E2E))
            ) {
                Text(
                    text = "${steps.size}",
                    color = TextSecondary,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(6.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            steps.forEachIndexed { idx, step ->
                Surface(
                    color = Color(0xFF1E1E1E),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, Color(0xFF2C2C2C))
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Surface(
                            color = Color(0xFF2A2A2A),
                            shape = CircleShape
                        ) {
                            Text(
                                text = "${idx + 1}",
                                color = TextPrimary,
                                fontSize = 9.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = step.name.replace('_', ' '),
                            color = TextPrimary,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.width(5.dp))
                        Text(
                            text = "${step.durationMs.toInt()}ms",
                            color = TextMuted,
                            fontSize = 9.sp
                        )
                    }
                }
            }
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Perplexity Follow-Up Interactive Prompts Section
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun PerplexityFollowUpSection(onSelectPrompt: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 10.dp)
    ) {
        Text(
            text = "Follow-up",
            color = TextSecondary,
            fontSize = 11.5.sp,
            fontWeight = FontWeight.SemiBold
        )
        Spacer(modifier = Modifier.height(6.dp))
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val suggestions = listOf(
                "Can you elaborate with technical detail?",
                "What are the key takeaways and trade-offs?",
                "Provide step-by-step implementation code"
            )
            suggestions.forEach { suggestion ->
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .clickable { onSelectPrompt(suggestion) },
                    color = Color(0xFF1C1C1C),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, Color(0xFF2A2A2A))
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.weight(1f)
                        ) {
                            Text(text = "+", color = TextSecondary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(text = suggestion, color = TextPrimary, fontSize = 12.sp)
                        }
                        Icon(
                            imageVector = Icons.Default.ArrowForward,
                            contentDescription = null,
                            tint = TextMuted,
                            modifier = Modifier.size(14.dp)
                        )
                    }
                }
            }
        }
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Continuous Multi-Step Tool Execution Chain Accordion (Gemini/Claude Style)
// ═════════════════════════════════════════════════════════════════════════════
@Composable
fun CyberToolChainAccordion(toolData: ToolData, onCopy: (String) -> Unit) {
    var isExpanded by remember { mutableStateOf(false) }
    val steps = toolData.steps
    val stepCount = steps.size
    val isError = toolData.status == "error" || steps.any { it.status == "error" }
    val accentColor = if (isError) NeonRed else NeonAmber

    Surface(
        color = VoidBlack.copy(alpha = 0.75f),
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, accentColor.copy(alpha = 0.5f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
            // Header Toggle Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .clickable { isExpanded = !isExpanded }
                    .padding(horizontal = 4.dp, vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(text = "⚡", fontSize = 12.sp)
                    Spacer(modifier = Modifier.width(6.dp))
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = if (stepCount > 1) {
                                    "CHAIN: $stepCount TOOLS EXECUTED"
                                } else {
                                    "TOOL: ${toolData.name.uppercase()}"
                                },
                                color = accentColor,
                                fontSize = 10.5.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.8.sp
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Surface(
                                color = if (isError) NeonRed.copy(alpha = 0.2f) else NeonGreen.copy(alpha = 0.2f),
                                shape = RoundedCornerShape(4.dp),
                                border = BorderStroke(0.8.dp, if (isError) NeonRed.copy(alpha = 0.5f) else NeonGreen.copy(alpha = 0.5f))
                            ) {
                                Text(
                                    text = if (isError) "ERR" else "OK",
                                    color = if (isError) NeonRed else NeonGreen,
                                    fontSize = 8.5.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                                )
                            }
                        }
                        if (stepCount > 1 && !isExpanded) {
                            val namesSummary = steps.joinToString(" ➔ ") { it.name.replace('_', ' ') }
                            Text(
                                text = namesSummary,
                                color = TextMuted,
                                fontSize = 9.5.sp,
                                fontFamily = FontFamily.Monospace,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "${toolData.durationMs.toInt()}ms",
                        color = TextMuted,
                        fontSize = 9.5.sp,
                        fontFamily = FontFamily.Monospace
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Icon(
                        imageVector = if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = if (isExpanded) "Collapse Tool Steps" else "Expand Tool Steps",
                        tint = accentColor,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }

            // Expandable Step-by-Step Breakdown
            AnimatedVisibility(
                visible = isExpanded,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(1.dp)
                            .background(PanelStrokeActive.copy(alpha = 0.3f))
                    )

                    steps.forEachIndexed { index, step ->
                        val isStepErr = step.status == "error"
                        Surface(
                            color = PanelDarkSolid,
                            shape = RoundedCornerShape(6.dp),
                            border = BorderStroke(1.dp, if (isStepErr) NeonRed.copy(alpha = 0.4f) else PanelStroke),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(8.dp)) {
                                // Step Header
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            text = "[STEP ${index + 1}]",
                                            color = NeonCyan,
                                            fontSize = 9.5.sp,
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            text = step.name,
                                            color = TextPrimary,
                                            fontSize = 10.5.sp,
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Medium
                                        )
                                    }
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            text = "${step.durationMs.toInt()}ms",
                                            color = TextMuted,
                                            fontSize = 9.sp,
                                            fontFamily = FontFamily.Monospace
                                        )
                                        Spacer(modifier = Modifier.width(4.dp))
                                        Text(
                                            text = if (isStepErr) "[FAIL]" else "[PASS]",
                                            color = if (isStepErr) NeonRed else NeonGreen,
                                            fontSize = 8.5.sp,
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                }

                                // Tool Arguments (if present)
                                if (step.args.isNotBlank()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Surface(
                                        color = VoidBlack,
                                        shape = RoundedCornerShape(4.dp),
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Text(
                                            text = "INPUT // ${step.args}",
                                            color = NeonCyanLight.copy(alpha = 0.85f),
                                            fontSize = 9.sp,
                                            fontFamily = FontFamily.Monospace,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 4.dp),
                                            maxLines = 3,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
                                }

                                // Tool Result / Observation Preview (if present)
                                if (step.preview.isNotBlank()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Surface(
                                        color = VoidBlack.copy(alpha = 0.9f),
                                        shape = RoundedCornerShape(4.dp),
                                        border = BorderStroke(0.5.dp, PanelStroke),
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 4.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Text(
                                                text = "OUTPUT // ${step.preview}",
                                                color = TextSecondary,
                                                fontSize = 9.sp,
                                                fontFamily = FontFamily.Monospace,
                                                modifier = Modifier.weight(1f),
                                                maxLines = 4,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                            IconButton(
                                                onClick = { onCopy(step.preview) },
                                                modifier = Modifier.size(18.dp)
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.ContentCopy,
                                                    contentDescription = "Copy Output",
                                                    tint = TextMuted,
                                                    modifier = Modifier.size(11.dp)
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
// Empty State Slate (Perplexity Discovery Greeting)
// ═════════════════════════════════════════════════════════════════
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
            modifier = Modifier.size(64.dp),
            shape = CircleShape,
            color = NeonCyanDim,
            border = BorderStroke(1.5.dp, NeonCyan.copy(alpha = 0.6f))
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = "✳️",
                    fontSize = 28.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Where knowledge begins",
            color = TextPrimary,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.5.sp,
            fontSize = 18.sp,
            fontFamily = FontFamily.SansSerif
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = "Ask anything, search deep academic intelligence, or analyze your current screen context.",
            color = TextSecondary,
            fontSize = 12.5.sp,
            textAlign = TextAlign.Center,
            lineHeight = 18.sp,
            modifier = Modifier.padding(horizontal = 20.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Perplexity-Style Discovery Starter Cards
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            SampleStarterChip("⚡ Run deep research on Quantum Computing 2026") {
                onSelectSample("/research Quantum Computing 2026 breakthroughs")
            }
            SampleStarterChip("🛡️ Run automated DAST security reconnaissance on localhost") {
                onSelectSample("/recon 127.0.0.1")
            }
            SampleStarterChip("☀️ Synthesize morning executive intelligence briefing") {
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
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PerplexityPillBorder)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.Explore,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = label,
                    color = TextPrimary,
                    fontSize = 12.5.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Icon(
                Icons.Default.ArrowForward,
                contentDescription = null,
                tint = TextMuted,
                modifier = Modifier.size(14.dp)
            )
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
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, PerplexityPillBorder)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(13.dp))
            Spacer(modifier = Modifier.width(6.dp))
            Text(text = text, color = TextHighlight, fontSize = 11.5.sp, fontWeight = FontWeight.Medium)
        }
    }
}
