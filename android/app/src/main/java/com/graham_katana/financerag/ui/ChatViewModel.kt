package com.graham_katana.financerag.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.ChatDetail
import com.graham_katana.financerag.data.ChatSummary
import com.graham_katana.financerag.data.FinanceApi
import com.graham_katana.financerag.data.Source
import com.graham_katana.financerag.data.StreamEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class UiMessage(
    val id: Long,
    val fromUser: Boolean,
    val text: String,
    val sources: List<Source> = emptyList(),
    /** For a follow-up, what was actually searched for. */
    val searchQuery: String? = null,
    val error: String? = null,
    val done: Boolean = true,
)

data class ChatUiState(
    val chatId: Long? = null,
    val messages: List<UiMessage> = emptyList(),
    val chats: List<ChatSummary> = emptyList(),
    val isStreaming: Boolean = false,
    val isLoadingChat: Boolean = false,
    val sessionExpired: Boolean = false,
)

class ChatViewModel(private val api: FinanceApi) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    /** Bumped whenever the visible chat changes, so an answer still arriving for the old one is ignored. */
    private var turn = 0
    private var nextLocalId = -1L

    init {
        refreshChats()
    }

    fun refreshChats() {
        viewModelScope.launch {
            try {
                val chats = api.chats()
                _state.update { it.copy(chats = chats) }
            } catch (e: ApiException) {
                noteSessionLoss(e) // a failed list is not worth interrupting the person for
            }
        }
    }

    fun newChat() {
        turn++
        _state.update { ChatUiState(chats = it.chats) }
    }

    fun openChat(id: Long) {
        val mine = ++turn
        _state.update { it.copy(chatId = id, messages = emptyList(), isStreaming = false, isLoadingChat = true) }
        viewModelScope.launch {
            try {
                val detail = api.chat(id)
                if (mine == turn) _state.update { it.copy(messages = toMessages(detail), isLoadingChat = false) }
            } catch (e: ApiException) {
                if (mine != turn) return@launch
                if (e is ApiException.NotFound) newChat() else {
                    _state.update { it.copy(isLoadingChat = false, messages = listOf(errorMessage(e))) }
                    noteSessionLoss(e)
                }
            }
        }
    }

    fun send(question: String) {
        val query = question.trim()
        val before = _state.value
        if (query.isEmpty() || before.isStreaming || before.isLoadingChat) return

        val mine = turn
        val answerId = nextLocalId--
        _state.update {
            it.copy(
                isStreaming = true,
                messages = it.messages + UiMessage(nextLocalId--, fromUser = true, text = query) + UiMessage(answerId, fromUser = false, text = "", done = false),
            )
        }

        viewModelScope.launch {
            var chatId = before.chatId
            fun patch(change: (UiMessage) -> UiMessage) = _state.update { s -> s.copy(messages = s.messages.map { if (it.id == answerId) change(it) else it }) }
            try {
                api.streamAnswer(query, TOP_N, before.chatId).collect { event ->
                    when (event) {
                        is StreamEvent.Chat -> {
                            chatId = event.id
                            if (mine == turn && _state.value.chatId == null) {
                                _state.update { it.copy(chatId = event.id) }
                                refreshChats() // the new chat appears in the list straight away
                            }
                        }
                        is StreamEvent.Text -> if (mine == turn) patch { it.copy(text = it.text + event.piece) }
                    }
                }
                if (mine != turn) return@launch
                patch { it.copy(done = true) }
                // The saved answer carries the exact passages it was built from, and what a follow-up was rewritten to.
                chatId?.let { id ->
                    try {
                        val last = api.chat(id).messages.lastOrNull { !it.role.equals("user", ignoreCase = true) }
                        if (mine == turn && last != null) patch { it.copy(sources = last.sources.orEmpty(), searchQuery = last.searchQuery) }
                    } catch (e: ApiException) {
                        noteSessionLoss(e) // the answer itself arrived; only its sources are missing
                    }
                }
                refreshChats()
            } catch (e: CancellationException) {
                throw e
            } catch (e: ApiException) {
                if (mine == turn) patch { it.copy(done = true, error = friendly(e)) }
                noteSessionLoss(e)
            } finally {
                if (mine == turn) _state.update { it.copy(isStreaming = false) }
            }
        }
    }

    private fun noteSessionLoss(e: ApiException) {
        if (e is ApiException.SessionExpired) _state.update { it.copy(sessionExpired = true) }
    }

    private fun friendly(e: ApiException): String = when (e) {
        is ApiException.NotFound -> "This chat no longer exists. Start a new chat to keep going."
        is ApiException.Http -> if (e.code >= 500) "Something went wrong on the server. Please try again." else e.message.orEmpty()
        else -> e.message.orEmpty()
    }

    private fun errorMessage(e: ApiException) = UiMessage(nextLocalId--, fromUser = false, text = "", error = friendly(e))

    private fun toMessages(detail: ChatDetail): List<UiMessage> = detail.messages.map {
        UiMessage(
            id = it.id,
            fromUser = it.role.equals("user", ignoreCase = true),
            text = it.content,
            sources = it.sources.orEmpty(),
            searchQuery = it.searchQuery,
        )
    }

    private companion object {
        const val TOP_N = 5
    }
}
