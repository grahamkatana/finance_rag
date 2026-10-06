package com.graham_katana.financerag.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.Document
import com.graham_katana.financerag.data.FinanceApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** The upload in progress, or the one that just finished or failed. */
data class UploadUi(
    val fileName: String,
    val message: String,
    /** 0..1 while the API reports how far it is; null while it does not. */
    val progress: Float? = null,
    val error: String? = null,
    val done: Boolean = false,
)

/** The "who can see this document" sheet. */
data class SharesUi(
    val fileName: String,
    val emails: List<String> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
)

data class DocumentsUiState(
    val documents: List<Document> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
    val upload: UploadUi? = null,
    val shares: SharesUi? = null,
    val sessionExpired: Boolean = false,
)

class DocumentsViewModel(private val api: FinanceApi) : ViewModel() {
    private val _state = MutableStateFlow(DocumentsUiState())
    val state: StateFlow<DocumentsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() = call(onError = { message -> _state.update { it.copy(isLoading = false, error = message) } }) {
        val documents = api.documents()
        _state.update { it.copy(documents = documents, isLoading = false, error = null) }
    }

    fun upload(fileName: String, bytes: ByteArray, source: String) {
        if (_state.value.upload?.let { !it.done && it.error == null } == true) return // one at a time
        _state.update { it.copy(upload = UploadUi(fileName, "Uploading…")) }
        fun patch(change: (UploadUi) -> UploadUi) = _state.update { s -> s.copy(upload = s.upload?.let(change)) }
        call(onError = { message -> patch { it.copy(error = message, progress = null) } }) {
            var finished = false
            api.uploadPdf(fileName, bytes, source.trim()).collect { event ->
                when (event.status) {
                    "done" -> { finished = true; patch { it.copy(message = "Ready to ask about.", progress = null, done = true) } }
                    "error" -> { finished = true; patch { it.copy(error = event.message.ifBlank { "The upload failed." }, progress = null) } }
                    else -> patch {
                        val total = event.total ?: 0
                        it.copy(message = event.message, progress = if (event.progress != null && total > 0) event.progress.toFloat() / total else null)
                    }
                }
            }
            // The connection closing early looks like a normal end of the stream, so "done" is the only proof it worked.
            if (!finished) patch { it.copy(error = "The upload was interrupted. Check the list before trying again.", progress = null) }
            refresh()
        }
    }

    fun dismissUpload() = _state.update { it.copy(upload = null) }

    fun delete(fileName: String) = call(onError = { message -> _state.update { it.copy(error = message) }; refresh() }) {
        api.deleteDocument(fileName)
        refresh()
    }

    fun openShares(fileName: String) {
        _state.update { it.copy(shares = SharesUi(fileName)) }
        loadShares(fileName)
    }

    fun closeShares() = _state.update { it.copy(shares = null) }

    fun share(email: String) = changeShares { api.share(it, email.trim()) }

    fun unshare(email: String) = changeShares { api.unshare(it, email) }

    private fun changeShares(change: suspend (String) -> Unit) {
        val fileName = _state.value.shares?.fileName ?: return
        patchShares(fileName) { it.copy(isLoading = true, error = null) }
        call(onError = { message -> patchShares(fileName) { it.copy(isLoading = false, error = message) } }) {
            change(fileName)
            loadShares(fileName)
        }
    }

    private fun loadShares(fileName: String) = call(onError = { message -> patchShares(fileName) { it.copy(isLoading = false, error = message) } }) {
        val emails = api.shares(fileName)
        patchShares(fileName) { it.copy(emails = emails, isLoading = false) }
    }

    /** Only touches the sheet if it is still showing [fileName]: an answer for a closed sheet is dropped. */
    private fun patchShares(fileName: String, change: (SharesUi) -> SharesUi) =
        _state.update { s -> if (s.shares?.fileName == fileName) s.copy(shares = change(s.shares)) else s }

    private fun call(onError: (String) -> Unit, block: suspend () -> Unit) {
        viewModelScope.launch {
            try {
                block()
            } catch (e: CancellationException) {
                throw e
            } catch (e: ApiException) {
                if (e is ApiException.SessionExpired) _state.update { it.copy(sessionExpired = true) }
                onError(
                    when {
                        // The only 404 the sharing calls give a person is an email with no account behind it.
                        e is ApiException.NotFound -> "No account uses that email address, or the document is gone."
                        e is ApiException.Http && e.code >= 500 -> "Something went wrong on the server. Please try again."
                        else -> e.message.orEmpty()
                    }
                )
            }
        }
    }
}
