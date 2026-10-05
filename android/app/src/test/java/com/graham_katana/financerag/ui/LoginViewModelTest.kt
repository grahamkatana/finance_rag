package com.graham_katana.financerag.ui

import com.graham_katana.financerag.data.ApiException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {
    private val api = FakeApi()
    private lateinit var vm: LoginViewModel

    @Before fun setUp() { Dispatchers.setMain(UnconfinedTestDispatcher()); vm = LoginViewModel(api) }
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun `a good login calls onSuccess and leaves no error`() {
        var succeeded = false
        vm.submit("  graham ", "pw") { succeeded = true }
        assertTrue(succeeded)
        assertEquals(listOf("graham" to "pw"), api.logins) // the username is trimmed, the password is not touched
        assertNull(vm.state.value.error)
        assertFalse(vm.state.value.isSubmitting)
    }

    @Test fun `a wrong password shows the API's message and does not continue`() {
        api.loginError = ApiException.InvalidCredentials()
        var succeeded = false
        vm.submit("graham", "bad") { succeeded = true }
        assertFalse(succeeded)
        assertEquals("Invalid username or password.", vm.state.value.error)
        assertFalse(vm.state.value.isSubmitting)
    }

    @Test fun `rate limiting and no connection each get their own message`() {
        api.loginError = ApiException.RateLimited()
        vm.submit("g", "p") {}
        assertTrue(vm.state.value.error!!.contains("rate limit"))
        api.loginError = ApiException.Network()
        vm.submit("g", "p") {}
        assertTrue(vm.state.value.error!!.contains("Can't reach the server"))
    }

    @Test fun `a server error is not shown raw`() {
        api.loginError = ApiException.Http(500, "Traceback (most recent call last)")
        vm.submit("g", "p") {}
        assertEquals("Something went wrong on the server. Please try again.", vm.state.value.error)
    }

    @Test fun `empty fields are rejected without calling the API`() {
        vm.submit("", "pw") {}
        vm.submit("graham", "") {}
        assertTrue(api.logins.isEmpty())
        assertEquals("Enter your username and password.", vm.state.value.error)
    }

    @Test fun `a login that cannot be stored securely is an error, not a crash`() {
        api.loginError = java.security.GeneralSecurityException("keystore refused")
        var succeeded = false
        vm.submit("graham", "pw") { succeeded = true }
        assertFalse(succeeded)
        assertTrue(vm.state.value.error!!.contains("could not store the login securely"))
        assertFalse(vm.state.value.isSubmitting)
    }
}
