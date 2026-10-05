package com.graham_katana.financerag.ui

import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.ChatDetail
import com.graham_katana.financerag.data.ChatSummary
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
    override fun logout() { loggedOut = true }
}
