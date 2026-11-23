package com.wealthorbit.android.vault

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.util.Base64

class VaultCryptoTest {
    // Mirrors testdata/vault_golden.json (produced by Python with fixed nonce).
    private val secret = "test-portfolio-secret-do-not-use-in-prod-32b"
    private val userId = "11111111-1111-1111-1111-111111111111"
    private val generation = 1
    private val plaintext =
        """{"schema_version":1,"exported_at":"2026-11-23T00:00:00+00:00","portfolio_id":"22222222-2222-2222-2222-222222222222","assets":[],"transactions":[],"holdings":[]}"""
    private val nonceHex = "0102030405060708090a0b0c"
    private val pythonCiphertextB64 =
        "AQECAwQFBgcICQoLDJJVI7cvgIHKvp/udIjhIhzFlVeqitE1u6zRjIPGcScJjc3IXXoyI2Gv3w8Qh9aLhxGnzFWIPRgw9XZ87F0g+Oz19aiLZi2q6xLs+NsXJBg+/f0gHaDGW2F2w9DSjk7BiuPvnZxWT76Px0Ava+0FtSh7uSs+BFW73c7KOgeUsdQxYIpnPGqtIXqRP29lNxSRpCPwHiYrFrJCfbtjMDTpT+Y10+wZNRF0qOIge1eW4IBf"
    private val keySha256Hex =
        "58996280321272257920c12d574b00492105b26542b597e475885f487e42d12d"

    @Test
    fun deriveKey_matchesPythonSha256() {
        val key = VaultCrypto.deriveKey(secret)
        assertEquals(32, key.size)
        assertEquals(keySha256Hex, key.joinToString("") { "%02x".format(it) })
    }

    @Test
    fun decrypt_pythonGoldenCiphertext() {
        val pt = VaultCrypto.decryptSnapshot(
            pythonCiphertextB64,
            secret = secret,
            userId = userId,
            vaultGeneration = generation,
        )
        assertEquals(plaintext, pt)
    }

    @Test
    fun encrypt_withFixedNonce_matchesPythonWire() {
        val nonce = nonceHex.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        val ct = VaultCrypto.encryptSnapshot(
            plaintext,
            secret = secret,
            userId = userId,
            vaultGeneration = generation,
            nonce = nonce,
        )
        assertEquals(pythonCiphertextB64, ct)
    }

    @Test
    fun roundTrip_randomNonce() {
        val ct = VaultCrypto.encryptSnapshot(
            plaintext,
            secret = secret,
            userId = userId,
            vaultGeneration = generation,
        )
        val raw = Base64.getDecoder().decode(ct)
        assertEquals(0x01.toByte(), raw[0])
        assertTrue(raw.size > 1 + 12 + 16)
        assertEquals(
            plaintext,
            VaultCrypto.decryptSnapshot(
                ct,
                secret = secret,
                userId = userId,
                vaultGeneration = generation,
            ),
        )
    }

    @Test
    fun wrongGeneration_fails() {
        val ct = VaultCrypto.encryptSnapshot(
            plaintext,
            secret = secret,
            userId = userId,
            vaultGeneration = generation,
        )
        try {
            VaultCrypto.decryptSnapshot(
                ct,
                secret = secret,
                userId = userId,
                vaultGeneration = generation + 1,
            )
            fail("expected AEAD failure")
        } catch (_: Exception) {
            // expected
        }
    }
}
