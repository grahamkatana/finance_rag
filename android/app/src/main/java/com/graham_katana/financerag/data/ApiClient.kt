package com.graham_katana.financerag.data

import java.io.IOException
import java.io.InputStreamReader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

@Serializable private data class LoginBody(val username: String, val password: String)
@Serializable private data class RefreshBody(@SerialName("refresh_token") val refreshToken: String)
@Serializable private data class ShareBody(@SerialName("file_name") val fileName: String, @SerialName("user_email") val userEmail: String)
@Serializable private data class GenerateBody(val query: String, @SerialName("top_n") val topN: Int, @SerialName("chat_id") val chatId: Long?)

/**
 * The finance_rag API. Authenticated calls carry the access token; when the
 * API answers 401 the refresh token is exchanged for a new pair and the call
 * is retried once, so an expired token is invisible to the person using the app.
 */
class ApiClient(
    /** Asked on every call, so a server address changed on the login screen takes effect at once. */
    private val baseUrl: () -> String,
    private val tokens: TokenStore,
    private val http: OkHttpClient = defaultHttp(),
) : FinanceApi {
    private val base: String get() = baseUrl().trimEnd('/')
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val jsonType = "application/json".toMediaType()
    // An upload sends megabytes, and the API can be silent for a while as it embeds a long document.
    private val uploadHttp = http.newBuilder()
        .writeTimeout(2, java.util.concurrent.TimeUnit.MINUTES)
        .readTimeout(10, java.util.concurrent.TimeUnit.MINUTES)
        .build()
    private val refreshLock = Mutex() // several calls can hit a 401 together; only one may spend the refresh token

    override suspend fun login(username: String, password: String) {
        val request = Request.Builder().url("$base/api/v1/auth/login")
            .post(json.encodeToString(LoginBody(username, password)).toRequestBody(jsonType)).build()
        withContext(Dispatchers.IO) {
            call(request).use { response ->
                when {
                    response.code == 401 -> throw ApiException.InvalidCredentials()
                    !response.isSuccessful -> throw failure(response)
                    else -> tokens.save(json.decodeFromString<Tokens>(response.body!!.string()))
                }
            }
        }
    }

    override fun logout() = tokens.clear()

    override suspend fun chats(): List<ChatSummary> =
        authed("/api/v1/chats") { json.decodeFromString<ChatList>(it.body!!.string()).chats }

    override suspend fun chat(id: Long): ChatDetail =
        authed("/api/v1/chats/$id") { json.decodeFromString<ChatDetail>(it.body!!.string()) }

    /**
     * Streams the answer. The API replies with plain text that arrives token by
     * token, and names the chat in the X-Chat-Id header (a new chat when [chatId]
     * is null), which is emitted first.
     */
    override fun streamAnswer(query: String, topN: Int, chatId: Long?): Flow<StreamEvent> = flow {
        val body = json.encodeToString(GenerateBody(query, topN, chatId)).toRequestBody(jsonType)
        sendAuthed { token -> Request.Builder().url("$base/api/v1/generation/generate").header("Authorization", "Bearer $token").post(body).build() }.use { response ->
            if (!response.isSuccessful) throw failure(response)
            response.header("X-Chat-Id")?.toLongOrNull()?.let { emit(StreamEvent.Chat(it)) }
            // A reader decodes UTF-8 across read boundaries, so a character split over two network reads stays whole.
            val reader = InputStreamReader(response.body!!.source().inputStream(), Charsets.UTF_8)
            val buffer = CharArray(1024)
            while (true) {
                val n = try { reader.read(buffer) } catch (e: IOException) { throw ApiException.Network() }
                if (n < 0) break
                if (n > 0) emit(StreamEvent.Text(String(buffer, 0, n)))
            }
        }
    }.flowOn(Dispatchers.IO)

    override suspend fun documents(): List<Document> =
        authed("/api/v1/ingestion/documents") { json.decodeFromString<DocumentList>(it.body!!.string()).documents }

    /**
     * The API answers with server-sent events, one `data: {json}` line per step.
     * A refusal before the work starts (not a PDF, already uploaded) is an ordinary HTTP error.
     */
    override fun uploadPdf(fileName: String, bytes: ByteArray, source: String): Flow<UploadEvent> = flow {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("source", source)
            .addFormDataPart("file", fileName, bytes.toRequestBody("application/pdf".toMediaType()))
            .build()
        sendAuthed(uploadHttp) { token -> Request.Builder().url("$base/api/v1/ingestion/upload").header("Authorization", "Bearer $token").post(body).build() }.use { response ->
            if (!response.isSuccessful) throw failure(response)
            val lines = response.body!!.source()
            while (true) {
                val line = try { lines.readUtf8Line() } catch (e: IOException) { throw ApiException.Network() } ?: break
                if (line.startsWith("data:")) emit(json.decodeFromString<UploadEvent>(line.removePrefix("data:").trim()))
            }
        }
    }.flowOn(Dispatchers.IO)

    override suspend fun deleteDocument(fileName: String) =
        authed("/api/v1/ingestion/documents/${segment(fileName)}", "DELETE") { }

    override suspend fun shares(fileName: String): List<String> =
        authed("/api/v1/ingestion/shares/${segment(fileName)}") { json.decodeFromString<ShareList>(it.body!!.string()).shares.mapNotNull { s -> s.email } }

    override suspend fun share(fileName: String, email: String) =
        authed("/api/v1/ingestion/shares", "POST", json.encodeToString(ShareBody(fileName, email)).toRequestBody(jsonType)) { }

    override suspend fun unshare(fileName: String, email: String) =
        authed("/api/v1/ingestion/shares", "DELETE", json.encodeToString(ShareBody(fileName, email)).toRequestBody(jsonType)) { }

    // ---- plumbing ----

    /** A file name as one URL path segment: spaces and slashes in it must not change the path. */
    private fun segment(name: String) = java.net.URLEncoder.encode(name, "UTF-8").replace("+", "%20")

    private suspend fun <T> authed(path: String, method: String = "GET", body: RequestBody? = null, parse: (Response) -> T): T = withContext(Dispatchers.IO) {
        sendAuthed { token -> Request.Builder().url("$base$path").header("Authorization", "Bearer $token").method(method, body).build() }.use { response ->
            if (!response.isSuccessful) throw failure(response)
            parse(response)
        }
    }

    /** Sends a request with the access token; on 401 refreshes once and retries. Blocking: call from IO. */
    private suspend fun sendAuthed(client: OkHttpClient = http, build: (String) -> Request): Response {
        val first = tokens.load() ?: throw ApiException.SessionExpired()
        val response = call(build(first.accessToken), client)
        if (response.code != 401) return response
        response.close()
        if (!refresh(staleAccessToken = first.accessToken)) throw ApiException.SessionExpired()
        val second = tokens.load() ?: throw ApiException.SessionExpired()
        val retry = call(build(second.accessToken), client)
        if (retry.code == 401) {
            retry.close()
            tokens.clear()
            throw ApiException.SessionExpired()
        }
        return retry
    }

    private suspend fun refresh(staleAccessToken: String): Boolean = refreshLock.withLock {
        val current = tokens.load() ?: return false
        if (current.accessToken != staleAccessToken) return true // another call already refreshed
        val request = Request.Builder().url("$base/api/v1/auth/refresh")
            .post(json.encodeToString(RefreshBody(current.refreshToken)).toRequestBody(jsonType)).build()
        call(request).use { response ->
            if (!response.isSuccessful) {
                tokens.clear()
                return false
            }
            tokens.save(json.decodeFromString<Tokens>(response.body!!.string()))
            return true
        }
    }

    private fun call(request: Request, client: OkHttpClient = http): Response = try {
        client.newCall(request).execute()
    } catch (e: IOException) {
        throw ApiException.Network()
    }

    private fun failure(response: Response): ApiException {
        val detail = detailOf(response)
        return when (response.code) {
            401 -> ApiException.SessionExpired()
            404 -> ApiException.NotFound()
            429 -> ApiException.RateLimited()
            503 -> ApiException.ServiceBusy(detail ?: "The service is busy. Please try again in a minute.")
            else -> ApiException.Http(response.code, detail ?: "Request failed (${response.code}).")
        }
    }

    /** FastAPI errors carry `detail` as a string, or as a list of validation problems. */
    private fun detailOf(response: Response): String? = try {
        when (val detail = (json.parseToJsonElement(response.body!!.string()) as? JsonObject)?.get("detail")) {
            is JsonPrimitive -> detail.contentOrNull
            is JsonArray -> detail.mapNotNull { (it as? JsonObject)?.get("msg")?.let { m -> (m as? JsonPrimitive)?.contentOrNull } }.joinToString("; ").ifBlank { null }
            else -> null
        }
    } catch (e: Exception) {
        null
    }

    companion object {
        fun defaultHttp(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
            // An answer can take a while to start (embedding, optional question rewrite) and then trickles in.
            .readTimeout(120, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }
}
