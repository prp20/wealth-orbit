package com.wealthorbit.android.db

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

data class AppConfig(
    val poolerUrl: String,
    val encryptionSecret: String,
    val vaultUserId: String,
    val groqApiKey: String = "",
)

class PoolerConfigStore(context: Context) {
    private val appContext = context.applicationContext
    private val prefs by lazy {
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            appContext,
            "wealth_orbit_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun isConfigured(): Boolean {
        val cfg = load()
        return cfg.poolerUrl.isNotBlank() &&
            cfg.encryptionSecret.isNotBlank() &&
            cfg.vaultUserId.isNotBlank()
    }

    fun load(): AppConfig = AppConfig(
        poolerUrl = prefs.getString(KEY_POOLER, "").orEmpty(),
        encryptionSecret = prefs.getString(KEY_SECRET, "").orEmpty(),
        vaultUserId = prefs.getString(KEY_USER, "").orEmpty(),
        groqApiKey = prefs.getString(KEY_GROQ, "").orEmpty(),
    )

    fun save(config: AppConfig) {
        require(config.poolerUrl.isNotBlank()) { "Pooler URL is required" }
        require(config.encryptionSecret.isNotBlank()) { "Encryption secret is required" }
        require(config.vaultUserId.isNotBlank()) { "VAULT_USER_ID is required" }
        prefs.edit()
            .putString(KEY_POOLER, config.poolerUrl.trim())
            .putString(KEY_SECRET, config.encryptionSecret)
            .putString(KEY_USER, config.vaultUserId.trim())
            .putString(KEY_GROQ, config.groqApiKey.trim())
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    companion object {
        private const val KEY_POOLER = "pooler_url"
        private const val KEY_SECRET = "encryption_secret"
        private const val KEY_USER = "vault_user_id"
        private const val KEY_GROQ = "groq_api_key"
    }
}
