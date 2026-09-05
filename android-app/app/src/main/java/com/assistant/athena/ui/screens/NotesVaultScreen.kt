package com.assistant.athena.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
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
import com.assistant.athena.data.NetworkClient
import com.assistant.athena.data.VaultNoteDetail
import com.assistant.athena.data.VaultNoteItem
import com.assistant.athena.ui.components.HudCard
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotesVaultScreen(
    networkClient: NetworkClient,
    onSelectSession: (String) -> Unit = {}
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var libraryTab by remember { mutableIntStateOf(0) } // 0: Threads, 1: Notes
    var sessions by remember { mutableStateOf<List<com.assistant.athena.data.SessionItem>>(emptyList()) }
    var isSessionsLoading by remember { mutableStateOf(false) }

    var notes by remember { mutableStateOf<List<VaultNoteItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf("all") }

    // Active note reader & editor modals
    var activeNoteDetail by remember { mutableStateOf<VaultNoteDetail?>(null) }
    var isReadingNote by remember { mutableStateOf(false) }

    var isEditingNote by remember { mutableStateOf(false) }
    var editTargetId by remember { mutableStateOf<String?>(null) }
    var editTitle by remember { mutableStateOf("") }
    var editCategory by remember { mutableStateOf("general") }
    var editTags by remember { mutableStateOf("") }
    var editContent by remember { mutableStateOf("") }

    val categories = listOf("all", "deep-research", "work", "ideas", "todos", "security-reports", "ctf", "general")

    fun reloadNotes() {
        coroutineScope.launch {
            isLoading = true
            notes = networkClient.fetchNotes()
            isLoading = false
        }
    }

    fun reloadSessions() {
        coroutineScope.launch {
            isSessionsLoading = true
            sessions = networkClient.fetchSessions()
            isSessionsLoading = false
        }
    }

    LaunchedEffect(Unit) {
        reloadSessions()
        reloadNotes()
    }

    val filteredNotes = remember(notes, searchQuery, selectedCategory) {
        notes.filter { note ->
            val matchCat = selectedCategory == "all" || note.category.equals(selectedCategory, ignoreCase = true)
            val matchQuery = searchQuery.isBlank() ||
                    note.title.contains(searchQuery, ignoreCase = true) ||
                    note.preview.contains(searchQuery, ignoreCase = true) ||
                    note.tags.any { it.contains(searchQuery, ignoreCase = true) }
            matchCat && matchQuery
        }
    }

    // Note Editor Sheet
    if (isEditingNote) {
        ModalBottomSheet(
            onDismissRequest = { isEditingNote = false },
            containerColor = DeepNavy,
            scrimColor = Color.Black.copy(alpha = 0.7f)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.9f)
                    .padding(horizontal = 20.dp, vertical = 12.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = if (editTargetId != null) "EDIT NOTE" else "CREATE VAULT NOTE",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp,
                    fontSize = 16.sp
                )

                Spacer(modifier = Modifier.height(16.dp))

                OutlinedTextField(
                    value = editTitle,
                    onValueChange = { editTitle = it },
                    label = { Text("Note Title", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(12.dp))

                // Category selector
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    categories.filter { it != "all" }.forEach { cat ->
                        FilterChip(
                            selected = editCategory == cat,
                            onClick = { editCategory = cat },
                            label = { Text(cat.uppercase(), fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = NeonCyan,
                                selectedLabelColor = VoidBlack,
                                containerColor = PanelDarkSolid,
                                labelColor = TextSecondary
                            )
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = editTags,
                    onValueChange = { editTags = it },
                    label = { Text("Tags (comma separated)", color = TextSecondary) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = editContent,
                    onValueChange = { editContent = it },
                    label = { Text("Markdown Content", color = TextSecondary) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(260.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = NeonCyan,
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Spacer(modifier = Modifier.height(20.dp))

                Button(
                    onClick = {
                        val tagsList = editTags.split(",").map { it.trim() }.filter { it.isNotEmpty() }
                        coroutineScope.launch {
                            val ok = networkClient.saveNote(
                                title = editTitle.trim(),
                                content = editContent,
                                category = editCategory,
                                tags = tagsList,
                                target = editTargetId
                            )
                            if (ok) {
                                isEditingNote = false
                                reloadNotes()
                                Toast.makeText(context, "Note saved to Vault", Toast.LENGTH_SHORT).show()
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = VoidBlack)
                ) {
                    Text("SAVE TO VAULT", fontWeight = FontWeight.Bold)
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }

    // Note Reader Sheet
    if (isReadingNote && activeNoteDetail != null) {
        val note = activeNoteDetail!!
        ModalBottomSheet(
            onDismissRequest = { isReadingNote = false },
            containerColor = DeepNavy,
            scrimColor = Color.Black.copy(alpha = 0.7f)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.9f)
                    .padding(horizontal = 20.dp, vertical = 12.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CategoryBadge(category = note.category)

                    Row {
                        IconButton(
                            onClick = {
                                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                cm.setPrimaryClip(ClipData.newPlainText("ATHENA Note", note.content))
                                Toast.makeText(context, "Copied content", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(Icons.Default.ContentCopy, contentDescription = "Copy", tint = TextSecondary, modifier = Modifier.size(16.dp))
                        }

                        IconButton(
                            onClick = {
                                editTargetId = note.id
                                editTitle = note.title
                                editCategory = note.category
                                editTags = note.tags.joinToString(", ")
                                editContent = note.content
                                isReadingNote = false
                                isEditingNote = true
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = "Edit", tint = NeonCyan, modifier = Modifier.size(16.dp))
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                Text(
                    text = note.title,
                    color = TextPrimary,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = "${note.path} // ${note.createdAt}",
                    color = TextMuted,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                if (note.tags.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        note.tags.forEach { tag ->
                            Surface(
                                color = NeonCyanDim,
                                shape = RoundedCornerShape(6.dp),
                                border = BorderStroke(1.dp, PanelStroke)
                            ) {
                                Text(
                                    text = "#$tag",
                                    color = NeonCyan,
                                    fontSize = 11.sp,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider(color = PanelStroke)
                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = note.content,
                    color = TextHighlight,
                    fontSize = 14.sp,
                    lineHeight = 22.sp
                )

                Spacer(modifier = Modifier.height(32.dp))
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // ═════ Header & Segment Row ═════
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = VoidBlack,
            border = BorderStroke(0.5.dp, PanelStroke)
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Library",
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp
                    )

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(
                            onClick = {
                                if (libraryTab == 0) reloadSessions() else reloadNotes()
                            },
                            modifier = Modifier.size(36.dp)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = TextSecondary, modifier = Modifier.size(18.dp))
                        }

                        if (libraryTab == 1) {
                            IconButton(
                                onClick = {
                                    editTargetId = null
                                    editTitle = ""
                                    editCategory = "general"
                                    editTags = ""
                                    editContent = ""
                                    isEditingNote = true
                                },
                                modifier = Modifier
                                    .size(32.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF242424))
                            ) {
                                Icon(Icons.Default.Add, contentDescription = "New Note", tint = TextPrimary, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Perplexity Library Segment Switch: [ Threads (N) ] | [ Notes (N) ]
                Surface(
                    shape = RoundedCornerShape(18.dp),
                    color = Color(0xFF1C1C1C),
                    border = BorderStroke(1.dp, Color(0xFF282828)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(3.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Surface(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(15.dp))
                                .clickable { libraryTab = 0 },
                            color = if (libraryTab == 0) Color(0xFF2C2C2C) else Color.Transparent,
                            shape = RoundedCornerShape(15.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(vertical = 7.dp),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Forum,
                                    contentDescription = null,
                                    tint = if (libraryTab == 0) TextPrimary else TextMuted,
                                    modifier = Modifier.size(15.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "Threads (${sessions.size})",
                                    fontSize = 12.sp,
                                    fontWeight = if (libraryTab == 0) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (libraryTab == 0) TextPrimary else TextMuted
                                )
                            }
                        }

                        Surface(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(15.dp))
                                .clickable { libraryTab = 1 },
                            color = if (libraryTab == 1) Color(0xFF2C2C2C) else Color.Transparent,
                            shape = RoundedCornerShape(15.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(vertical = 7.dp),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Book,
                                    contentDescription = null,
                                    tint = if (libraryTab == 1) TextPrimary else TextMuted,
                                    modifier = Modifier.size(15.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "Notes (${notes.size})",
                                    fontSize = 12.sp,
                                    fontWeight = if (libraryTab == 1) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (libraryTab == 1) TextPrimary else TextMuted
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    placeholder = {
                        Text(
                            text = if (libraryTab == 0) "Search past conversation threads..." else "Search notes, tags, or research...",
                            color = TextMuted,
                            fontSize = 13.sp
                        )
                    },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = TextMuted, modifier = Modifier.size(18.dp)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF3F3F46),
                        unfocusedBorderColor = PanelStroke,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedContainerColor = Color(0xFF161616),
                        unfocusedContainerColor = Color(0xFF161616)
                    )
                )

                if (libraryTab == 1) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        categories.forEach { cat ->
                            FilterChip(
                                selected = selectedCategory == cat,
                                onClick = { selectedCategory = cat },
                                label = { Text(cat.uppercase(), fontSize = 11.sp) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = Color(0xFF2C2C2C),
                                    selectedLabelColor = TextPrimary,
                                    containerColor = Color(0xFF181818),
                                    labelColor = TextSecondary
                                )
                            )
                        }
                    }
                }
            }
        }

        // ═════ Feed Area (Threads or Notes) ═════
        Box(modifier = Modifier.weight(1f)) {
            if (libraryTab == 0) {
                // ─── THREADS LIST ───
                val filteredSessions = remember(sessions, searchQuery) {
                    if (searchQuery.isBlank()) sessions
                    else sessions.filter { it.title.contains(searchQuery, ignoreCase = true) }
                }

                if (isSessionsLoading) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = TextPrimary, modifier = Modifier.size(32.dp))
                    }
                } else if (filteredSessions.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.Forum, contentDescription = null, tint = TextMuted, modifier = Modifier.size(40.dp))
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                text = if (searchQuery.isNotBlank()) "No threads match '$searchQuery'" else "No conversation threads yet",
                                color = TextMuted,
                                fontSize = 13.sp
                            )
                        }
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 14.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(filteredSessions, key = { it.id }) { session ->
                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onSelectSession(session.id) },
                                color = Color(0xFF1A1A1A),
                                shape = RoundedCornerShape(14.dp),
                                border = BorderStroke(1.dp, Color(0xFF282828))
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 14.dp, vertical = 12.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = session.title,
                                            color = TextPrimary,
                                            fontWeight = FontWeight.SemiBold,
                                            fontSize = 14.sp,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                        Spacer(modifier = Modifier.height(3.dp))
                                        Text(
                                            text = "${session.messageCount} messages • Tap to open",
                                            color = TextMuted,
                                            fontSize = 11.sp
                                        )
                                    }
                                    IconButton(
                                        onClick = {
                                            coroutineScope.launch {
                                                networkClient.deleteSession(session.id)
                                                reloadSessions()
                                            }
                                        },
                                        modifier = Modifier.size(32.dp)
                                    ) {
                                        Icon(
                                            Icons.Default.DeleteOutline,
                                            contentDescription = "Delete",
                                            tint = TextMuted,
                                            modifier = Modifier.size(18.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                // ─── NOTES LIST ───
                if (isLoading) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = TextPrimary, modifier = Modifier.size(32.dp))
                    }
                } else if (filteredNotes.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            text = if (searchQuery.isNotBlank()) "No notes match query" else "No notes in this category",
                            color = TextMuted
                        )
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(filteredNotes, key = { it.id }) { note ->
                            NoteCardItem(
                                note = note,
                                onClick = {
                                    coroutineScope.launch {
                                        val detail = networkClient.readNote(note.id)
                                        if (detail != null) {
                                            activeNoteDetail = detail
                                            isReadingNote = true
                                        }
                                    }
                                },
                                onDelete = {
                                    coroutineScope.launch {
                                        val ok = networkClient.deleteNote(note.id)
                                        if (ok) reloadNotes()
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

@Composable
fun NoteCardItem(
    note: VaultNoteItem,
    onClick: () -> Unit,
    onDelete: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = PerplexitySurfaceElevated,
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PerplexityPillBorder)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                CategoryBadge(category = note.category)

                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (note.sourcesCount != null) {
                        Surface(
                            color = NeonAmber.copy(alpha = 0.15f),
                            shape = RoundedCornerShape(6.dp),
                            border = BorderStroke(1.dp, NeonAmber.copy(alpha = 0.4f))
                        ) {
                            Text(
                                text = "${note.sourcesCount} Sources",
                                color = NeonAmber,
                                fontSize = 10.sp,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                    }

                    IconButton(onClick = onDelete, modifier = Modifier.size(24.dp)) {
                        Icon(Icons.Default.Delete, contentDescription = "Delete", tint = NeonRed.copy(alpha = 0.6f), modifier = Modifier.size(14.dp))
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = note.title,
                color = TextPrimary,
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            if (note.preview.isNotEmpty()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = note.preview,
                    color = TextSecondary,
                    fontSize = 12.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    lineHeight = 16.sp
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = note.createdAt,
                    color = TextMuted,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                if (note.tags.isNotEmpty()) {
                    Text(
                        text = note.tags.take(3).joinToString(" ") { "#$it" },
                        color = NeonCyan,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
    }
}

@Composable
fun CategoryBadge(category: String) {
    val (color, icon) = when (category.lowercase()) {
        "deep-research" -> Pair(Color(0xFFBA68FF), "🔬")
        "work" -> Pair(Color(0xFFFFC24B), "⚡")
        "ideas" -> Pair(Color(0xFF4DFF91), "💡")
        "todos" -> Pair(Color(0xFFFF5D5D), "✅")
        "security-reports" -> Pair(Color(0xFFFF9900), "🛡️")
        "ctf", "lab-dossiers" -> Pair(Color(0xFFFF3366), "🎯")
        else -> Pair(NeonCyan, "📄")
    }

    Surface(
        color = color.copy(alpha = 0.15f),
        shape = RoundedCornerShape(6.dp),
        border = BorderStroke(1.dp, color.copy(alpha = 0.45f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = icon, fontSize = 11.sp)
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = category.uppercase(),
                color = color,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}
