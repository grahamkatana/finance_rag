package com.graham_katana.financerag.ui

import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.ChatDetail
import com.graham_katana.financerag.data.ChatMessageDto
import com.graham_katana.financerag.data.ChatSummary
import com.graham_katana.financerag.data.Source
import com.graham_katana.financerag.data.StreamEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.consumeAsFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {
    private val api = FakeApi()
    private val source = Source("Services net sales were 96,169.", "10k.pdf", 3, "sec.gov", 0.03)

    @Before fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    private fun vm() = ChatViewModel(api)
    private fun answered(id: Long, text: String, sources: List<Source>? = null, searchQuery: String? = null) =
        ChatDetail(id, "title", listOf(ChatMessageDto(1, "user", "q"), ChatMessageDto(2, "assistant", text, sources, searchQuery)))

    @Test fun `an answer streams in, the chat is created, and its sources arrive after it finishes`() {
        api.stream = { _, _, _ -> flow { emit(StreamEvent.Chat(7)); emit(StreamEvent.Text("Net sales ")); emit(StreamEvent.Text("were 391B.")) } }
        api.details[7] = answered(7, "Net sales were 391B.", listOf(source))
        api.chatList = listOf(ChatSummary(7, "What was net sales?"))
        val vm = vm()
        vm.send("What was net sales?")
        val state = vm.state.value
        assertEquals(7L, state.chatId)
        assertEquals(listOf(true, false), state.messages.map { it.fromUser })
        assertEquals("Net sales were 391B.", state.messages[1].text)
        assertEquals(listOf(source), state.messages[1].sources)
        assertTrue(state.messages[1].done)
        assertFalse(state.isStreaming)
        assertEquals(listOf("What was net sales?"), state.chats.map { it.title }) // the new chat is in the list
    }

    @Test fun `text appears while the answer is still arriving`() {
        val live = Channel<StreamEvent>(Channel.UNLIMITED)
        api.stream = { _, _, _ -> live.consumeAsFlow() }
        val vm = vm()
        vm.send("q")
        assertTrue(vm.state.value.isStreaming)
        live.trySend(StreamEvent.Text("Part one. "))
        assertEquals("Part one. ", vm.state.value.messages.last().text)
        assertFalse(vm.state.value.messages.last().done)
        live.trySend(StreamEvent.Text("Part two."))
        assertEquals("Part one. Part two.", vm.state.value.messages.last().text)
        live.close()
        assertFalse(vm.state.value.isStreaming)
    }

    @Test fun `a follow-up continues the same chat and shows how it was understood`() {
        api.stream = { _, _, chatId -> flow { emit(StreamEvent.Chat(chatId ?: 7)); emit(StreamEvent.Text("answer")) } }
        api.details[7] = answered(7, "answer", listOf(source), searchQuery = "What were Apple's services net sales in fiscal 2024?")
        val vm = vm()
        vm.send("What was net sales?")
        vm.send("And services?")
        assertEquals(listOf(null, 7L), api.asked.map { it.third })
        assertEquals("What were Apple's services net sales in fiscal 2024?", vm.state.value.messages.last().searchQuery)
    }

    @Test fun `blank input and a second question while one is streaming are ignored`() {
        api.stream = { _, _, _ -> Channel<StreamEvent>().consumeAsFlow() } // never finishes
        val vm = vm()
        vm.send("   ")
        assertTrue(api.asked.isEmpty())
        vm.send("first")
        vm.send("second")
        assertEquals(listOf("first"), api.asked.map { it.first })
    }

    @Test fun `a rate limit becomes a friendly message on the answer, not a crash`() {
        api.stream = { _, _, _ -> flow { throw ApiException.RateLimited() } }
        val vm = vm()
        vm.send("q")
        val answer = vm.state.value.messages.last()
        assertTrue(answer.error!!.contains("rate limit"))
        assertTrue(answer.done)
        assertFalse(vm.state.value.isStreaming)
        assertFalse(vm.state.value.sessionExpired)
    }

    @Test fun `the API's own explanation for a busy service is shown as it is`() {
        api.stream = { _, _, _ -> flow { throw ApiException.ServiceBusy("The search service is busy. Please wait a minute and try again.") } }
        val vm = vm()
        vm.send("q")
        assertEquals("The search service is busy. Please wait a minute and try again.", vm.state.value.messages.last().error)
    }

    @Test fun `an answer cut off by a lost connection keeps what arrived and says so`() {
        api.stream = { _, _, _ -> flow { emit(StreamEvent.Chat(1)); emit(StreamEvent.Text("Half an ans")); throw ApiException.Network() } }
        val vm = vm()
        vm.send("q")
        val answer = vm.state.value.messages.last()
        assertEquals("Half an ans", answer.text)
        assertTrue(answer.error!!.contains("Can't reach the server"))
    }

    @Test fun `losing the session is flagged so the app can return to login`() {
        api.stream = { _, _, _ -> flow { throw ApiException.SessionExpired() } }
        val vm = vm()
        vm.send("q")
        assertTrue(vm.state.value.sessionExpired)
    }

    @Test fun `if only the source lookup fails the answer itself is kept`() {
        api.stream = { _, _, _ -> flow { emit(StreamEvent.Chat(7)); emit(StreamEvent.Text("the answer")) } }
        api.detailError = ApiException.Network()
        val vm = vm()
        vm.send("q")
        val answer = vm.state.value.messages.last()
        assertEquals("the answer", answer.text)
        assertNull(answer.error)
        assertTrue(answer.sources.isEmpty())
    }

    @Test fun `opening a saved chat shows its messages with sources and rewritten queries`() {
        api.details[5] = ChatDetail(5, "t", listOf(
            ChatMessageDto(1, "user", "And services?"),
            ChatMessageDto(2, "assistant", "Services were 96B.", listOf(source), "What were services net sales?"),
        ))
        val vm = vm()
        vm.openChat(5)
        val state = vm.state.value
        assertEquals(5L, state.chatId)
        assertFalse(state.isLoadingChat)
        assertEquals(listOf(true, false), state.messages.map { it.fromUser })
        assertEquals(listOf(source), state.messages[1].sources)
        assertEquals("What were services net sales?", state.messages[1].searchQuery)
    }

    @Test fun `opening a chat that has been deleted falls back to a new chat`() {
        val vm = vm() // no details registered: the API answers NotFound
        vm.openChat(99)
        assertNull(vm.state.value.chatId)
        assertTrue(vm.state.value.messages.isEmpty())
        assertFalse(vm.state.value.isLoadingChat)
    }

    @Test fun `new chat clears the conversation and the next question starts a fresh chat`() {
        api.stream = { _, _, _ -> flow { emit(StreamEvent.Chat(7)); emit(StreamEvent.Text("x")) } }
        api.details[7] = answered(7, "x")
        api.chatList = listOf(ChatSummary(7, "old"))
        val vm = vm()
        vm.send("one")
        vm.newChat()
        assertNull(vm.state.value.chatId)
        assertTrue(vm.state.value.messages.isEmpty())
        assertEquals(1, vm.state.value.chats.size) // the list is kept
        vm.send("two")
        assertNull(api.asked.last().third)
    }

    @Test fun `an answer still arriving for a chat you left does not leak into the one you opened`() {
        val live = Channel<StreamEvent>(Channel.UNLIMITED)
        api.stream = { _, _, _ -> live.consumeAsFlow() }
        api.details[2] = ChatDetail(2, "other", listOf(ChatMessageDto(1, "user", "other question")))
        val vm = vm()
        vm.send("q in the first chat")
        vm.openChat(2)
        live.trySend(StreamEvent.Text("late tokens for the old chat"))
        live.close()
        assertEquals(listOf("other question"), vm.state.value.messages.map { it.text })
        assertFalse(vm.state.value.isStreaming) // you can ask in the chat you opened
    }

    @Test fun `a failed chat list does not interrupt anything, but an expired session is noticed`() {
        api.chatsError = ApiException.Network()
        assertFalse(vm().state.value.sessionExpired)
        api.chatsError = ApiException.SessionExpired()
        assertTrue(vm().state.value.sessionExpired)
    }
}
