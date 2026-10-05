package com.graham_katana.financerag.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Tokens(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
)

/** A passage the answer was built from. "Source 1" in an answer is the first of these. */
@Serializable
data class Source(
    @SerialName("chunk_text") val chunkText: String,
    @SerialName("file_name") val fileName: String,
    @SerialName("chunk_index") val chunkIndex: Int,
    val source: String = "",
    val score: Double = 0.0,
)

@Serializable
data class ChatSummary(
    val id: Long,
    val title: String,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
internal data class ChatList(val chats: List<ChatSummary>)

@Serializable
data class ChatMessageDto(
    val id: Long,
    val role: String,
    val content: String,
    val sources: List<Source>? = null,
    /** For a follow-up: the standalone question the API actually searched for. */
    @SerialName("search_query") val searchQuery: String? = null,
)

@Serializable
data class ChatDetail(
    val id: Long,
    val title: String,
    val messages: List<ChatMessageDto>,
)

/** What streaming an answer produces, in order: the chat's id once, then the text in pieces. */
sealed interface StreamEvent {
    data class Chat(val id: Long) : StreamEvent
    data class Text(val piece: String) : StreamEvent
}

/** Everything the API can refuse with, mapped to what the screen needs to say. */
sealed class ApiException(message: String) : Exception(message) {
    class InvalidCredentials : ApiException("Invalid username or password.")
    class SessionExpired : ApiException("Your session has expired. Please log in again.")
    class RateLimited : ApiException("You're going faster than the rate limit allows. Give it a minute and try again.")
    /** The API's own explanation, e.g. the search service is busy. */
    class ServiceBusy(detail: String) : ApiException(detail)
    class NotFound : ApiException("Not found.")
    class Network : ApiException("Can't reach the server. Check your connection and try again.")
    class Http(val code: Int, detail: String) : ApiException(detail)
}

/** The calls the screens depend on; [ApiClient] is the real one, tests use a fake. */
interface FinanceApi {
    suspend fun login(username: String, password: String)
    fun streamAnswer(query: String, topN: Int, chatId: Long?): kotlinx.coroutines.flow.Flow<StreamEvent>
    suspend fun chats(): List<ChatSummary>
    suspend fun chat(id: Long): ChatDetail
    fun logout()
}
