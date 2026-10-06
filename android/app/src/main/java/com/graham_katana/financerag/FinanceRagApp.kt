package com.graham_katana.financerag

import android.app.Application
import com.graham_katana.financerag.data.ApiClient
import com.graham_katana.financerag.data.KeystoreTokenStore
import com.graham_katana.financerag.data.ServerSettings

class FinanceRagApp : Application() {
    val tokens by lazy { KeystoreTokenStore(this) }
    val server by lazy { ServerSettings(this, defaultUrl = BuildConfig.API_BASE_URL, allowHttp = BuildConfig.DEBUG) }
    val api by lazy { ApiClient({ server.url.value }, tokens) }
}
