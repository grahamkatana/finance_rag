package com.graham_katana.financerag.data

class FakeTokenStore(private var tokens: Tokens? = null) : TokenStore {
    override fun load() = tokens
    override fun save(tokens: Tokens) { this.tokens = tokens }
    override fun clear() { tokens = null }
}
