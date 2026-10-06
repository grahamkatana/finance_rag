package com.graham_katana.financerag

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import android.graphics.Color
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.graham_katana.financerag.ui.ChatScreen
import com.graham_katana.financerag.ui.ChatViewModel
import com.graham_katana.financerag.ui.DocumentsScreen
import com.graham_katana.financerag.ui.DocumentsViewModel
import com.graham_katana.financerag.ui.FinanceRagTheme
import com.graham_katana.financerag.ui.LoginScreen
import com.graham_katana.financerag.ui.LoginViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // The app is dark, so the bars are always drawn dark with light icons. The default follows the
        // phone's light/dark setting, which on a phone in light mode paints a pale bar over a dark app.
        // Transparent bars let the app's own colours show through: the top bar's green runs up under
        // the status bar, and the bottom input bar's colour runs down under the navigation bar.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        val app = application as FinanceRagApp
        setContent {
            FinanceRagTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    var loggedIn by remember { mutableStateOf(app.tokens.load() != null) }
                    // A new number per login, so a new person never sees the previous person's chats.
                    var session by remember { mutableIntStateOf(0) }
                    var showDocuments by remember { mutableStateOf(false) }
                    if (loggedIn) {
                        val chat: ChatViewModel = viewModel(key = "chat-$session", factory = viewModelFactory { initializer { ChatViewModel(app.api) } })
                        val documents: DocumentsViewModel = viewModel(key = "documents-$session", factory = viewModelFactory { initializer { DocumentsViewModel(app.api) } })
                        val logout: () -> Unit = { app.api.logout(); loggedIn = false; showDocuments = false; session++ }
                        // The documents model outlives its screen, so an upload keeps going while you go back to the chat.
                        if (showDocuments) DocumentsScreen(documents, onBack = { showDocuments = false }, onLogout = logout)
                        else ChatScreen(chat, onDocuments = { documents.refresh(); showDocuments = true }, onLogout = logout)
                    } else {
                        val login: LoginViewModel = viewModel(key = "login-$session", factory = viewModelFactory { initializer { LoginViewModel(app.api) } })
                        LoginScreen(login, app.server, onLoggedIn = { loggedIn = true })
                    }
                }
            }
        }
    }
}
