package com.graham_katana.financerag.ui

import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.Document
import com.graham_katana.financerag.data.UploadEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DocumentsViewModelTest {
    private val api = FakeApi()
    private val tenK = Document("10k.pdf", "sec.gov", 42, isOwner = true)

    @Before fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun `a finished upload is marked done and appears in the list`() {
        val vm = DocumentsViewModel(api)
        api.upload = flow {
            emit(UploadEvent("saving", "Writing chunks…", progress = 10, total = 40))
            assertEquals(0.25f, vm.state.value.upload!!.progress)
            api.documentList = listOf(tenK)
            emit(UploadEvent("done", "Ingestion complete"))
        }
        vm.upload("10k.pdf", ByteArray(1), " sec.gov ")
        assertTrue(vm.state.value.upload!!.done)
        assertNull(vm.state.value.upload!!.error)
        assertEquals(listOf(tenK), vm.state.value.documents)
    }

    @Test fun `an error step is shown as the reason`() {
        val vm = DocumentsViewModel(api)
        api.upload = flowOf(UploadEvent("extracting", "Extracting…"), UploadEvent("error", "No text could be extracted"))
        vm.upload("scan.pdf", ByteArray(1), "x")
        assertEquals("No text could be extracted", vm.state.value.upload!!.error)
    }

    @Test fun `a stream that ends without done is not reported as a success`() {
        val vm = DocumentsViewModel(api)
        api.upload = flowOf(UploadEvent("embedding", "Embedding 40 chunks…"))
        vm.upload("10k.pdf", ByteArray(1), "x")
        assertTrue(vm.state.value.upload!!.error!!.contains("interrupted"))
        assertTrue(!vm.state.value.upload!!.done)
    }

    @Test fun `a refused upload shows what the API said`() {
        val vm = DocumentsViewModel(api)
        api.upload = flow { throw ApiException.Http(409, "10k.pdf has already been ingested. Delete it first to re-ingest.") }
        vm.upload("10k.pdf", ByteArray(1), "x")
        assertTrue(vm.state.value.upload!!.error!!.contains("already been ingested"))
    }

    @Test fun `sharing adds the address, unsharing removes it, and an unknown address is explained`() {
        val vm = DocumentsViewModel(api)
        vm.openShares("10k.pdf")
        vm.share(" ann@example.com ")
        assertEquals(listOf("ann@example.com"), vm.state.value.shares!!.emails)

        api.shareError = ApiException.NotFound()
        vm.share("nobody@example.com")
        assertTrue(vm.state.value.shares!!.error!!.contains("No account"))
        assertEquals(listOf("ann@example.com"), vm.state.value.shares!!.emails)

        vm.unshare("ann@example.com")
        assertEquals(emptyList<String>(), vm.state.value.shares!!.emails)
    }

    @Test fun `deleting removes the document from the list`() {
        api.documentList = listOf(tenK)
        val vm = DocumentsViewModel(api)
        vm.delete("10k.pdf")
        assertEquals(listOf("10k.pdf"), api.deleted)
        assertTrue(vm.state.value.documents.isEmpty())
    }

    @Test fun `an expired session is flagged so the app returns to login`() {
        api.upload = flow { throw ApiException.SessionExpired() }
        val vm = DocumentsViewModel(api)
        vm.upload("10k.pdf", ByteArray(1), "x")
        assertTrue(vm.state.value.sessionExpired)
    }
}
