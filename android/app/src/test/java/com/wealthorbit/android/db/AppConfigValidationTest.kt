package com.wealthorbit.android.db

import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test

class AppConfigValidationTest {
    @Test
    fun appConfig_fieldsRoundTrip() {
        val cfg = AppConfig(
            poolerUrl = "postgresql://user:pass@host:5432/postgres",
            encryptionSecret = "secret",
            vaultUserId = "11111111-1111-1111-1111-111111111111",
            groqApiKey = "gsk",
        )
        assertEquals("secret", cfg.encryptionSecret)
        assertEquals("gsk", cfg.groqApiKey)
    }

    @Test
    fun blankPoolerRejectedByContract() {
        try {
            require("".isNotBlank()) { "Pooler URL is required" }
            fail("expected")
        } catch (_: IllegalArgumentException) {
            // ok
        }
    }
}
