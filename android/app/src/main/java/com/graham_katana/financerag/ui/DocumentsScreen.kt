package com.graham_katana.financerag.ui

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.graham_katana.financerag.data.Document
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

// ponytail: the file is held in memory to send it; a streamed request body if people need bigger PDFs.
private const val MAX_PDF_BYTES = 50L * 1024 * 1024

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocumentsScreen(viewModel: DocumentsViewModel, onBack: () -> Unit, onLogout: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var picked by remember { mutableStateOf<Uri?>(null) }
    var pickedName by remember { mutableStateOf("") }
    var source by rememberSaveable { mutableStateOf("") }
    var pickError by remember { mutableStateOf<String?>(null) }
    var deleting by remember { mutableStateOf<String?>(null) }

    BackHandler(onBack = onBack)
    LaunchedEffect(state.sessionExpired) { if (state.sessionExpired) onLogout() }

    // The system file picker: no storage permission needed, and it only offers PDFs (all the API accepts).
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            picked = uri
            pickedName = displayName(context, uri)
            source = ""
            pickError = null
        }
    }
    val uploading = state.upload?.let { !it.done && it.error == null } == true

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Documents") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to chat") } },
                actions = { IconButton(onClick = { picker.launch(arrayOf("application/pdf")) }, enabled = !uploading) { Icon(Icons.Default.Add, "Upload a PDF") } },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Green,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                    navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                    actionIconContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            state.upload?.let { item(key = "upload") { UploadCard(it, onDismiss = viewModel::dismissUpload) } }
            (pickError ?: state.error)?.let { item(key = "error") { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) } }
            when {
                state.isLoading -> item { Text("Loading documents…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                state.documents.isEmpty() -> item {
                    Column(Modifier.fillMaxWidth().padding(top = 48.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("No documents yet", style = MaterialTheme.typography.titleMedium)
                        Text("Upload a PDF to ask questions about it.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Button(onClick = { picker.launch(arrayOf("application/pdf")) }, enabled = !uploading) { Text("Upload a PDF") }
                    }
                }
                else -> items(state.documents, key = { it.fileName + "\n" + it.source }) { document ->
                    DocumentRow(document, onShare = { viewModel.openShares(document.fileName) }, onDelete = { deleting = document.fileName })
                }
            }
        }
    }

    // Step two of an upload: the API wants to know where the document came from.
    picked?.let { uri ->
        AlertDialog(
            onDismissRequest = { picked = null },
            title = { Text("Upload a PDF") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(pickedName, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    OutlinedTextField(value = source, onValueChange = { source = it }, label = { Text("Where is it from?") }, placeholder = { Text("e.g. https://investor.apple.com") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
            },
            confirmButton = {
                TextButton(
                    enabled = source.isNotBlank(),
                    colors = paperText(),
                    onClick = {
                        val name = pickedName
                        val from = source
                        picked = null
                        scope.launch {
                            val bytes = withContext(Dispatchers.IO) { readPdf(context, uri) }
                            if (bytes == null) pickError = "That file could not be read, or is larger than 50 MB." else viewModel.upload(name, bytes, from)
                        }
                    },
                ) { Text("Upload") }
            },
            dismissButton = { TextButton(onClick = { picked = null }, colors = paperText()) { Text("Cancel") } },
        )
    }

    deleting?.let { fileName ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete this document?") },
            text = { Text("$fileName will be removed, and nobody it is shared with will be able to ask about it. This cannot be undone.") },
            confirmButton = { TextButton(onClick = { viewModel.delete(fileName); deleting = null }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { deleting = null }, colors = paperText()) { Text("Cancel") } },
        )
    }

    state.shares?.let { shares ->
        ModalBottomSheet(onDismissRequest = viewModel::closeShares) { SharesSheet(shares, onShare = viewModel::share, onUnshare = viewModel::unshare) }
    }
}

@Composable
private fun paperText() = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurface)

@Composable
private fun UploadCard(upload: UploadUi, onDismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(12.dp)).padding(start = 14.dp, top = 6.dp, bottom = 12.dp, end = 4.dp)) {
        Row(Modifier.heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(upload.fileName, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            // An upload cannot be cancelled half-way, so the card can only be closed once it has ended.
            if (upload.done || upload.error != null) IconButton(onClick = onDismiss) { Icon(Icons.Default.Close, "Dismiss") }
        }
        if (upload.error != null) {
            Text(upload.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(end = 10.dp))
        } else {
            Text(upload.message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(end = 10.dp))
            if (!upload.done) {
                val bar = Modifier.fillMaxWidth().padding(top = 10.dp, end = 10.dp)
                if (upload.progress != null) LinearProgressIndicator(progress = { upload.progress }, modifier = bar) else LinearProgressIndicator(modifier = bar)
            }
        }
    }
}

@Composable
private fun DocumentRow(document: Document, onShare: () -> Unit, onDelete: () -> Unit) {
    Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(12.dp)).padding(start = 14.dp, top = 10.dp, bottom = 10.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(document.fileName, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            val details = listOfNotNull(document.source.ifBlank { null }, "${document.chunkCount} passages", if (document.isOwner) null else "shared with you")
            Text(details.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        // Only the owner can share or delete; the API refuses anyone else.
        if (document.isOwner) {
            IconButton(onClick = onShare) { Icon(Icons.Default.Share, "Share ${document.fileName}") }
            IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, "Delete ${document.fileName}") }
        }
    }
}

@Composable
private fun SharesSheet(shares: SharesUi, onShare: (String) -> Unit, onUnshare: (String) -> Unit) {
    var email by rememberSaveable(shares.fileName) { mutableStateOf("") }
    // Clear the box once the address shows up in the list, and keep it when the API refused it.
    LaunchedEffect(shares.emails) { if (shares.emails.any { it.equals(email.trim(), ignoreCase = true) }) email = "" }

    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Share", style = MaterialTheme.typography.titleMedium)
        Text(shares.fileName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Their email address") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, autoCorrectEnabled = false),
                modifier = Modifier.weight(1f),
            )
            Button(onClick = { onShare(email) }, enabled = email.isNotBlank() && !shares.isLoading) { Text("Share") }
        }
        shares.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        HorizontalDivider(color = MaterialTheme.colorScheme.outline)
        when {
            shares.emails.isNotEmpty() -> shares.emails.forEach { address ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(address, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    IconButton(onClick = { onUnshare(address) }, enabled = !shares.isLoading) { Icon(Icons.Default.Close, "Stop sharing with $address") }
                }
            }
            shares.isLoading -> Text("Loading…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> Text("Only you can see this document.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun displayName(context: Context, uri: Uri): String =
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(0) else null
    } ?: "document.pdf"

/** Null when the file cannot be read or is over the limit. Reads one byte past the limit to tell. Blocking: call from IO. */
private fun readPdf(context: Context, uri: Uri): ByteArray? = try {
    context.contentResolver.openInputStream(uri)?.use { input ->
        val out = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(64 * 1024)
        while (out.size() <= MAX_PDF_BYTES) {
            val n = input.read(buffer)
            if (n < 0) return@use out.toByteArray()
            out.write(buffer, 0, n)
        }
        null
    }
} catch (e: Exception) {
    null
}
