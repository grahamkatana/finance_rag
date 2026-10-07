package com.graham_katana.financerag.ui

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.DisposableEffect
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.graham_katana.financerag.data.Source
import kotlinx.coroutines.launch

private val SUGGESTIONS = listOf(
    "What was total net sales in the most recent fiscal year?",
    "What are the main risk factors disclosed?",
    "How did gross margin change, and what drove it?",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(viewModel: ChatViewModel, onDocuments: () -> Unit, onLogout: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    var draft by rememberSaveable { mutableStateOf("") }
    var readAloud by rememberSaveable { mutableStateOf(false) }
    val speaker = rememberSpeaker()
    val feed = remember { SpeechFeed() }
    var streamedId by remember { mutableStateOf<Long?>(null) }
    var dictationBase by remember { mutableStateOf("") }
    val listener = rememberListener { text, _ -> draft = (dictationBase + " " + text).trim() }
    val askMic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) { speaker.stop(); dictationBase = draft; listener.start() } }
    val tapMic = {
        when {
            listener.listening -> listener.stop()
            listener.permitted -> { speaker.stop(); dictationBase = draft; listener.start() }
            else -> askMic.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
    // Read a new answer aloud as it arrives, one sentence at a time. An answer that was already on screen is never read unasked.
    val last = state.messages.lastOrNull()
    LaunchedEffect(last?.id, last?.text, state.isStreaming, readAloud) {
        if (last == null || last.fromUser) return@LaunchedEffect
        if (state.isStreaming) streamedId = last.id
        if (readAloud && streamedId == last.id) feed.next(last.id, last.text, !state.isStreaming)?.let(speaker::say)
    }
    LaunchedEffect(readAloud) { if (!readAloud) speaker.stop() }
    LaunchedEffect(state.chatId, state.isLoadingChat) { speaker.stop(); feed.reset(); streamedId = null }
    var openSource by remember { mutableStateOf<Pair<Int, Source>?>(null) }

    LaunchedEffect(state.sessionExpired) { if (state.sessionExpired) onLogout() }
    // Follow the answer as it streams in.
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.text?.length) {
        if (state.messages.isNotEmpty()) listState.scrollToItem(state.messages.lastIndex)
    }

    val send = {
        val text = draft
        if (text.isNotBlank() && !state.isStreaming && !state.isLoadingChat) {
            speaker.stop(); feed.reset(); if (listener.listening) listener.stop()
            viewModel.send(text)
            draft = ""
        }
    }

    ModalNavigationDrawer(
        drawerState = drawer,
        drawerContent = {
            ModalDrawerSheet {
                Column(Modifier.fillMaxSize().padding(vertical = 12.dp)) {
                    Text("Finance RAG", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp))
                    OutlinedButton(
                        onClick = { viewModel.newChat(); scope.launch { drawer.close() } },
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.onSurface),
                        modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                    ) { Icon(Icons.Default.Add, null); Text("  New chat") }
                    Text("Chats", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 24.dp, top = 16.dp, bottom = 4.dp))
                    LazyColumn(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                        items(state.chats, key = { it.id }) { chat ->
                            NavigationDrawerItem(
                                label = { Text(chat.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                                selected = chat.id == state.chatId,
                                onClick = { viewModel.openChat(chat.id); scope.launch { drawer.close() } },
                            )
                        }
                        if (state.chats.isEmpty()) item { Text("Your chats will appear here.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(12.dp)) }
                    }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                    TextButton(onClick = { onDocuments(); scope.launch { drawer.close() } }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurface), modifier = Modifier.padding(horizontal = 8.dp)) { Text("Documents") }
                    TextButton(onClick = onLogout, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurface), modifier = Modifier.padding(horizontal = 8.dp)) { Text("Log out") }
                }
            }
        },
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text(state.chats.firstOrNull { it.id == state.chatId }?.title ?: "New chat", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    navigationIcon = { IconButton(onClick = { scope.launch { drawer.open() } }) { Icon(Icons.Default.Menu, "Chats") } },
                    actions = {
                        IconButton(onClick = { readAloud = !readAloud }) { Icon(VoiceIcons.Speaker, if (readAloud) "Turn off read aloud" else "Read answers aloud", tint = LocalContentColor.current.copy(alpha = if (readAloud) 1f else 0.45f)) }
                        IconButton(onClick = viewModel::newChat) { Icon(Icons.Default.Add, "New chat") }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Green,
                        scrolledContainerColor = Green,
                        titleContentColor = MaterialTheme.colorScheme.onBackground,
                        navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                        actionIconContentColor = MaterialTheme.colorScheme.onBackground,
                    ),
                )
            },
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.navigationBarsPadding().imePadding()) {
                    ChatInput(
                        draft = draft,
                        onDraft = { draft = it },
                        placeholder = if (listener.listening) "Listening…" else listener.error ?: "Ask about your documents…",
                        listening = listener.listening,
                        canSend = draft.isNotBlank() && !state.isStreaming && !state.isLoadingChat,
                        busy = state.isStreaming || state.isLoadingChat,
                        onSend = send,
                        onMic = tapMic,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    )
                }
            },
            contentWindowInsets = WindowInsets(0, 0, 0, 0),
        ) { padding ->
            Box(Modifier.padding(padding).fillMaxSize()) {
                when {
                    state.isLoadingChat -> Text("Loading chat…", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.align(Alignment.Center))
                    state.messages.isEmpty() -> EmptyState(onPick = { viewModel.send(it) })
                    else -> LazyColumn(state = listState, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                        items(state.messages, key = { it.id }) { message ->
                            if (message.fromUser) UserBubble(message) else AnswerView(message, onSource = { index, source -> openSource = index to source }, speaker = speaker, onSpeak = { feed.reset(); streamedId = null })
                        }
                    }
                }
            }
        }
    }

    openSource?.let { (index, source) ->
        ModalBottomSheet(onDismissRequest = { openSource = null }) {
            Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Source $index", style = MaterialTheme.typography.titleMedium)
                Text(source.fileName, style = MaterialTheme.typography.bodyMedium)
                Text("Passage ${source.chunkIndex}" + if (source.source.isNotBlank()) " · from ${source.source}" else "", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                SelectionContainer { Text(source.chunkText, style = MaterialTheme.typography.bodyMedium) }
            }
        }
    }
}

@Composable
private fun EmptyState(onPick: (String) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Text("Ask your financial documents something", style = MaterialTheme.typography.titleMedium)
        Text("Answers use only documents you can access, and cite their sources.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp, bottom = 20.dp))
        SUGGESTIONS.forEach { suggestion ->
            OutlinedButton(onClick = { onPick(suggestion) }, shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.onSurface), modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                Text(suggestion, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun UserBubble(message: UiMessage) {
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
        Text(
            message.text,
            color = MaterialTheme.colorScheme.onPrimary,
            modifier = Modifier.widthIn(max = 300.dp).background(MaterialTheme.colorScheme.primary, RoundedCornerShape(18.dp, 18.dp, 4.dp, 18.dp)).padding(horizontal = 14.dp, vertical = 10.dp),
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AnswerView(message: UiMessage, onSource: (Int, Source) -> Unit, speaker: Speaker, onSpeak: () -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        when {
            message.error != null -> Text(message.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            message.text.isEmpty() -> Text("Searching your documents…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> SelectionContainer { MarkdownText(message.text) }
        }
        if (message.done && message.error == null && message.text.isNotEmpty()) ReadButton(speaker) { speaker.stop(); onSpeak(); speaker.say(speakable(message.text)) }
        // For a follow-up, show what was actually searched for, so a misread question is easy to spot.
        message.searchQuery?.takeIf { it.isNotBlank() }?.let {
            Text("Searched for: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (message.sources.isNotEmpty()) {
            val files = message.sources.withIndex().groupBy({ it.value.fileName }, { it })
            Text("SOURCES · ${files.size} ${if (files.size == 1) "document" else "documents"}, ${message.sources.size} passages", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            files.forEach { (fileName, passages) ->
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(8.dp)).padding(horizontal = 10.dp, vertical = 8.dp),
                ) {
                    Text(fileName, style = MaterialTheme.typography.bodySmall, modifier = Modifier.align(Alignment.CenterVertically).widthIn(max = 220.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                    passages.forEach { (index, source) ->
                        Box(
                            Modifier.heightIn(min = 28.dp).background(MaterialTheme.colorScheme.primary, CircleShape).clickable { onSource(index + 1, source) }.padding(horizontal = 11.dp),
                            contentAlignment = Alignment.Center,
                        ) { Text("${index + 1}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimary) }
                    }
                }
            }
        }
    }
}

/** Reads one answer aloud, or stops the voice if it is already talking. */
@Composable
private fun ReadButton(speaker: Speaker, onRead: () -> Unit) {
    if (!speaker.ready) return
    TextButton(
        onClick = { if (speaker.speaking) speaker.stop() else onRead() },
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
        colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurfaceVariant),
    ) {
        Icon(if (speaker.speaking) VoiceIcons.Stop else VoiceIcons.Speaker, null, Modifier.size(18.dp))
        Text(if (speaker.speaking) "  Stop" else "  Read aloud", style = MaterialTheme.typography.labelMedium)
    }
}
