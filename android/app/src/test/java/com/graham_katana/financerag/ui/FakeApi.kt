package com.graham_katana.financerag.ui

import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.ChatDetail
import com.graham_katana.financerag.data.ChatSummary
import com.graham_katana.financerag.data.Document
import com.graham_katana.financerag.data.UploadEvent
import com.graham_katana.financerag.data.FinanceApi
import com.graham_katana.financerag.data.StreamEvent
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow

class FakeApi : FinanceApi {
    var chatList: List<ChatSummary> = emptyList()
    var chatsError: ApiException? = null
    val details = mutableMapOf<Long, ChatDetail>()
    var detailError: ApiException? = null
    var loginError: Exception? = null
    var stream: (String, Int, Long?) -> Flow<StreamEvent> = { _, _, _ -> emptyFlow() }

    val asked = mutableListOf<Triple<String, Int, Long?>>()
    val logins = mutableListOf<Pair<String, String>>()
    var loggedOut = false

    override suspend fun login(username: String, password: String) {
        logins += username to password
        loginError?.let { throw it }
    }
    override fun streamAnswer(query: String, topN: Int, chatId: Long?): Flow<StreamEvent> {
        asked += Triple(query, topN, chatId)
        return stream(query, topN, chatId)
    }
    override suspend fun chats(): List<ChatSummary> = chatsError?.let { throw it } ?: chatList
    override suspend fun chat(id: Long): ChatDetail = detailError?.let { throw it } ?: details[id] ?: throw ApiException.NotFound()
    var documentList: List<Document> = emptyList()
    var upload: Flow<UploadEvent> = emptyFlow()
    val sharedWith = mutableMapOf<String, MutableList<String>>()
    var shareError: ApiException? = null
    val deleted = mutableListOf<String>()

    override suspend fun documents(): List<Document> = documentList
    override fun uploadPdf(fileName: String, bytes: ByteArray, source: String): Flow<UploadEvent> = upload
    override suspend fun deleteDocument(fileName: String) { deleted += fileName; documentList = documentList.filter { it.fileName != fileName } }
    override suspend fun shares(fileName: String): List<String> = sharedWith[fileName].orEmpty().toList()
    override suspend fun share(fileName: String, email: String) { shareError?.let { throw it }; sharedWith.getOrPut(fileName) { mutableListOf() } += email }
    override suspend fun unshare(fileName: String, email: String) { sharedWith[fileName]?.remove(email) }
    override fun logout() { loggedOut = true }
}
