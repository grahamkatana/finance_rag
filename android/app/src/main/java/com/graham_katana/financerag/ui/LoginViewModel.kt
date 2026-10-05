package com.graham_katana.financerag.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.graham_katana.financerag.data.ApiException
import com.graham_katana.financerag.data.FinanceApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LoginUiState(val isSubmitting: Boolean = false, val error: String? = null)

class LoginViewModel(private val api: FinanceApi) : ViewModel() {
    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun submit(username: String, password: String, onSuccess: () -> Unit) {
        if (_state.value.isSubmitting) return
        if (username.isBlank() || password.isEmpty()) {
            _state.update { it.copy(error = "Enter your username and password.") }
            return
        }
        _state.update { LoginUiState(isSubmitting = true) }
        viewModelScope.launch {
            try {
                api.login(username.trim(), password)
                _state.update { LoginUiState() }
                onSuccess()
            } catch (e: ApiException) {
                _state.update { LoginUiState(error = if (e is ApiException.Http && e.code >= 500) "Something went wrong on the server. Please try again." else e.message) }
            } catch (e: Exception) {
                // The server said yes but the login could not be saved (e.g. the device's keystore refused).
                // Say so: carrying on would only fail on the very next call.
                _state.update { LoginUiState(error = "Logged in, but this device could not store the login securely. Please try again.") }
            }
        }
    }
}
