package com.graham_katana.financerag.data

import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ApiClientTest {
    private lateinit var server: MockWebServer
    private lateinit var tokens: FakeTokenStore
    private lateinit var api: ApiClient

    private val tokenJson = """{"access_token":"new-access","refresh_token":"new-refresh","token_type":"bearer"}"""
    private val chatsJson = """{"chats":[{"id":1,"title":"First","created_at":"x","updated_at":"y"}],"total":1}"""

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        tokens = FakeTokenStore(Tokens("old-access", "old-refresh"))
        api = ApiClient({ server.url("/").toString() }, tokens)
    }

    @After fun tearDown() = server.shutdown()

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    // ---- login ----

    @Test fun `login stores the tokens`() = runTest {
        tokens.clear()
        server.enqueue(json(tokenJson))
        api.login("graham", "pw")
        assertEquals(Tokens("new-access", "new-refresh"), tokens.load())
        val sent = server.takeRequest()
        assertEquals("/api/v1/auth/login", sent.path)
        assertEquals("""{"username":"graham","password":"pw"}""", sent.body.readUtf8())
    }

    @Test fun `a wrong password is InvalidCredentials and stores nothing`() = runTest {
        tokens.clear()
        server.enqueue(json("""{"detail":"Invalid username or password"}""", 401))
        assertThrows(ApiException.InvalidCredentials::class.java) { kotlinx.coroutines.runBlocking { api.login("graham", "wrong") } }
        assertNull(tokens.load())
    }

    @Test fun `too many login attempts is RateLimited`() = runTest {
        server.enqueue(json("""{"detail":"Rate limit exceeded. Try again later."}""", 429))
        assertThrows(ApiException.RateLimited::class.java) { kotlinx.coroutines.runBlocking { api.login("a", "b") } }
    }

    @Test fun `an unreachable server is a Network error`() = runTest {
        server.shutdown()
        assertThrows(ApiException.Network::class.java) { kotlinx.coroutines.runBlocking { api.login("a", "b") } }
    }

    // ---- token refresh ----

    private fun dispatchWithRefresh(refreshCalls: AtomicInteger, refreshOk: Boolean = true) {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when {
                request.path == "/api/v1/auth/refresh" -> { refreshCalls.incrementAndGet(); if (refreshOk) json(tokenJson) else json("""{"detail":"Invalid refresh token"}""", 401) }
                request.getHeader("Authorization") == "Bearer new-access" -> json(chatsJson)
                else -> json("""{"detail":"Could not validate credentials"}""", 401)
            }
        }
    }

    @Test fun `an expired access token is refreshed and the call retried without the caller noticing`() = runTest {
        val refreshes = AtomicInteger()
        dispatchWithRefresh(refreshes)
        assertEquals("First", api.chats().single().title)
        assertEquals(1, refreshes.get())
        assertEquals("new-access", tokens.load()!!.accessToken)
    }

    @Test fun `calls that hit a 401 together spend the refresh token only once`() = runTest {
        val refreshes = AtomicInteger()
        dispatchWithRefresh(refreshes)
        List(4) { async { api.chats() } }.awaitAll()
        assertEquals(1, refreshes.get())
    }

    @Test fun `when the refresh token is rejected the session is over and the tokens are cleared`() = runTest {
        dispatchWithRefresh(AtomicInteger(), refreshOk = false)
        assertThrows(ApiException.SessionExpired::class.java) { kotlinx.coroutines.runBlocking { api.chats() } }
        assertNull(tokens.load())
    }

    @Test fun `with no saved login a call is SessionExpired and sends nothing`() = runTest {
        tokens.clear()
        assertThrows(ApiException.SessionExpired::class.java) { kotlinx.coroutines.runBlocking { api.chats() } }
        assertEquals(0, server.requestCount)
    }

    @Test fun `logout forgets the tokens`() {
        api.logout()
        assertNull(tokens.load())
    }

    // ---- reads ----

    @Test fun `a saved chat parses with its sources and the rewritten search query`() = runTest {
        server.enqueue(json("""{"id":7,"title":"T","created_at":"x","updated_at":"y","messages":[
            {"id":1,"role":"user","content":"And services?","sources":null,"search_query":null,"created_at":"x"},
            {"id":2,"role":"assistant","content":"Services were ${'$'}96.2B.","sources":[{"chunk_text":"Services net sales were 96,169.","file_name":"10k.pdf","chunk_index":3,"source":"sec.gov","score":0.03}],"search_query":"What were Apple's services net sales?","created_at":"x"}]}"""))
        val chat = api.chat(7)
        assertEquals("What were Apple's services net sales?", chat.messages[1].searchQuery)
        assertEquals("10k.pdf", chat.messages[1].sources!!.single().fileName)
        assertNull(chat.messages[0].sources)
        assertEquals("Bearer old-access", server.takeRequest().getHeader("Authorization"))
    }

    @Test fun `a chat that is not found is NotFound`() = runTest {
        server.enqueue(json("""{"detail":"Chat not found"}""", 404))
        assertThrows(ApiException.NotFound::class.java) { kotlinx.coroutines.runBlocking { api.chat(99) } }
    }

    // ---- streaming ----

    private fun textStream(body: String, chatId: String? = null) = MockResponse().setHeader("Content-Type", "text/plain").apply {
        chatId?.let { setHeader("X-Chat-Id", it) }
        setBody(body)
    }

    @Test fun `the chat id comes first and then the text`() = runTest {
        server.enqueue(textStream("Net sales were 391 billion.", chatId = "42"))
        val events = api.streamAnswer("What was net sales?", 5, null).toList()
        assertEquals(StreamEvent.Chat(42), events.first())
        assertEquals("Net sales were 391 billion.", events.drop(1).joinToString("") { (it as StreamEvent.Text).piece })
    }

    @Test fun `a character split across network reads stays whole`() = runTest {
        val text = "Revenue grew 12% — total €391bn ✓ done"
        // Two bytes at a time: "—", "€" and "✓" are 3 bytes each, so every one is cut in half by a read.
        server.enqueue(MockResponse().setHeader("X-Chat-Id", "1").setBody(Buffer().write(text.toByteArray())).throttleBody(2, 5, TimeUnit.MILLISECONDS))
        val pieces = api.streamAnswer("q", 5, null).toList().filterIsInstance<StreamEvent.Text>()
        assertTrue("expected the text to arrive in several pieces", pieces.size > 3)
        assertEquals(text, pieces.joinToString("") { it.piece })
    }

    @Test fun `the request carries the bearer token, the question and the chat being continued`() = runTest {
        server.enqueue(textStream("ok", chatId = "7"))
        api.streamAnswer("And services?", 5, 7).toList()
        val sent = server.takeRequest()
        assertEquals("Bearer old-access", sent.getHeader("Authorization"))
        assertEquals("/api/v1/generation/generate", sent.path)
        assertEquals("""{"query":"And services?","top_n":5,"chat_id":7}""", sent.body.readUtf8())
    }

    @Test fun `a first question sends no chat id`() = runTest {
        server.enqueue(textStream("ok", chatId = "1"))
        api.streamAnswer("q", 5, null).toList()
        assertFalse(server.takeRequest().body.readUtf8().contains("chat_id"))
    }

    @Test fun `streaming recovers from an expired token before the answer starts`() = runTest {
        val refreshes = AtomicInteger()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when {
                request.path == "/api/v1/auth/refresh" -> { refreshes.incrementAndGet(); json(tokenJson) }
                request.getHeader("Authorization") == "Bearer new-access" -> textStream("fine", chatId = "3")
                else -> json("""{"detail":"expired"}""", 401)
            }
        }
        val events = api.streamAnswer("q", 5, null).toList()
        assertEquals(1, refreshes.get())
        assertEquals(StreamEvent.Chat(3), events.first())
    }

    @Test fun `a rate limit while asking is RateLimited`() = runTest {
        server.enqueue(json("""{"detail":"Rate limit exceeded. Try again later."}""", 429))
        assertThrows(ApiException.RateLimited::class.java) { kotlinx.coroutines.runBlocking { api.streamAnswer("q", 5, null).toList() } }
    }

    @Test fun `a busy search service surfaces the API's own explanation`() = runTest {
        server.enqueue(json("""{"detail":"The search service is busy or over its rate limit. Please wait a minute and try again."}""", 503))
        val error = assertThrows(ApiException.ServiceBusy::class.java) { kotlinx.coroutines.runBlocking { api.streamAnswer("q", 5, null).toList() } }
        assertEquals("The search service is busy or over its rate limit. Please wait a minute and try again.", error.message)
    }

    @Test fun `validation errors are read from FastAPI's list form`() = runTest {
        server.enqueue(json("""{"detail":[{"msg":"String should have at least 1 character"},{"msg":"Field required"}]}""", 422))
        val error = assertThrows(ApiException.Http::class.java) { kotlinx.coroutines.runBlocking { api.streamAnswer("", 5, null).toList() } }
        assertEquals("String should have at least 1 character; Field required", error.message)
    }

    @Test fun `continuing a chat that no longer exists is NotFound`() = runTest {
        server.enqueue(json("""{"detail":"Chat not found"}""", 404))
        assertThrows(ApiException.NotFound::class.java) { kotlinx.coroutines.runBlocking { api.streamAnswer("q", 5, 99).toList() } }
    }

    // ---- documents ----

    @Test fun `an upload sends the PDF and its source, and reports each step`() = runTest {
        server.enqueue(MockResponse().setHeader("Content-Type", "text/event-stream").setBody(
            "data: {\"status\": \"saving\", \"message\": \"Writing\", \"progress\": 10, \"total\": 40}\n\n" +
                "data: {\"status\": \"done\", \"message\": \"Ingestion complete\", \"file_name\": \"10k.pdf\", \"chunks_ingested\": 40}\n\n"
        ))
        val events = api.uploadPdf("10k.pdf", "%PDF-1.7".toByteArray(), "sec.gov").toList()
        assertEquals(listOf(UploadEvent("saving", "Writing", 10, 40), UploadEvent("done", "Ingestion complete")), events)
        val sent = server.takeRequest()
        assertEquals("/api/v1/ingestion/upload", sent.path)
        assertEquals("Bearer old-access", sent.getHeader("Authorization"))
        val body = sent.body.readUtf8()
        assertTrue(body.contains("name=\"source\"") && body.contains("sec.gov"))
        assertTrue(body.contains("filename=\"10k.pdf\"") && body.contains("Content-Type: application/pdf") && body.contains("%PDF-1.7"))
    }

    @Test fun `an upload the API refuses carries its explanation`() = runTest {
        server.enqueue(json("""{"detail":"10k.pdf has already been ingested. Delete it first to re-ingest."}""", 409))
        val e = assertThrows(ApiException.Http::class.java) { kotlinx.coroutines.runBlocking { api.uploadPdf("10k.pdf", ByteArray(1), "x").toList() } }
        assertEquals(409, e.code)
        assertTrue(e.message!!.contains("already been ingested"))
    }

    @Test fun `a file name with spaces and a slash stays one path segment`() = runTest {
        server.enqueue(json("""{"file_name":"a","chunks_deleted":3}"""))
        api.deleteDocument("Q4 report/final.pdf")
        val sent = server.takeRequest()
        assertEquals("DELETE", sent.method)
        assertEquals("/api/v1/ingestion/documents/Q4%20report%2Ffinal.pdf", sent.path)
    }

    @Test fun `documents and shares are read, and sharing is by email`() = runTest {
        server.enqueue(json("""{"documents":[{"file_name":"10k.pdf","source":"sec.gov","chunk_count":40,"created_at":null,"is_owner":true}],"total":1}"""))
        assertEquals(listOf(Document("10k.pdf", "sec.gov", 40, true)), api.documents())
        server.takeRequest()

        server.enqueue(json("""{"file_name":"10k.pdf","shares":[{"granted_to_user_id":2,"email":"ann@example.com","created_at":null},{"granted_to_user_id":3,"email":null}]}"""))
        assertEquals(listOf("ann@example.com"), api.shares("10k.pdf"))
        server.takeRequest()

        server.enqueue(json("""{"file_name":"10k.pdf","shared_with":2}"""))
        api.share("10k.pdf", "ann@example.com")
        val shared = server.takeRequest()
        assertEquals("POST /api/v1/ingestion/shares", "${shared.method} ${shared.path}")
        assertEquals("""{"file_name":"10k.pdf","user_email":"ann@example.com"}""", shared.body.readUtf8())

        server.enqueue(json("""{"file_name":"10k.pdf","removed":1}"""))
        api.unshare("10k.pdf", "ann@example.com")
        val removed = server.takeRequest()
        assertEquals("DELETE /api/v1/ingestion/shares", "${removed.method} ${removed.path}")
        assertEquals("""{"file_name":"10k.pdf","user_email":"ann@example.com"}""", removed.body.readUtf8())
    }
}
