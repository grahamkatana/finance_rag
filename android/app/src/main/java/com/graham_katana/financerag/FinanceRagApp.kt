package com.graham_katana.financerag

import android.app.Application
import com.graham_katana.financerag.data.ApiClient
import com.graham_katana.financerag.data.KeystoreTokenStore

class FinanceRagApp : Application() {
    val tokens by lazy { KeystoreTokenStore(this) }
    val api by lazy { ApiClient(BuildConfig.API_BASE_URL, tokens) }
}
