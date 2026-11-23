package com.wealthorbit.android.vault

import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * AES-256-GCM portfolio vault crypto matching Python `backend.vault.crypto`
 * and docs/design/portfolio-vault-crypto.md.
 *
 * Wire: Base64( version=0x01 || 12-byte nonce || ciphertext||tag )
 * AAD:  UTF-8 `wealth-orbit-portfolio-v1|{user_id}|{vault_generation}`
 * Key:  SHA-256(UTF-8 secret)
 */
object VaultCrypto {
    private const val VERSION: Byte = 0x01
    private const val NONCE_LEN = 12
    private const val TAG_BITS = 128
    private const val AAD_PREFIX = "wealth-orbit-portfolio-v1"

    fun deriveKey(secret: String): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(secret.toByteArray(StandardCharsets.UTF_8))
    }

    fun aad(userId: String, vaultGeneration: Int): ByteArray =
        "$AAD_PREFIX|$userId|$vaultGeneration".toByteArray(StandardCharsets.UTF_8)

    fun encryptSnapshot(
        plaintextJson: String,
        secret: String,
        userId: String,
        vaultGeneration: Int,
        nonce: ByteArray? = null,
    ): String {
        val key = deriveKey(secret)
        val iv = nonce ?: ByteArray(NONCE_LEN).also { SecureRandom().nextBytes(it) }
        require(iv.size == NONCE_LEN) { "nonce must be 12 bytes" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(TAG_BITS, iv))
        cipher.updateAAD(aad(userId, vaultGeneration))
        val body = cipher.doFinal(plaintextJson.toByteArray(StandardCharsets.UTF_8))
        val wire = ByteBuffer.allocate(1 + NONCE_LEN + body.size)
            .put(VERSION)
            .put(iv)
            .put(body)
            .array()
        return Base64.getEncoder().encodeToString(wire)
    }

    fun decryptSnapshot(
        ciphertextB64: String,
        secret: String,
        userId: String,
        vaultGeneration: Int,
    ): String {
        val raw = Base64.getDecoder().decode(ciphertextB64)
        if (raw.size < 1 + NONCE_LEN + 16 || raw[0] != VERSION) {
            throw IllegalArgumentException("unsupported ciphertext")
        }
        val nonce = raw.copyOfRange(1, 1 + NONCE_LEN)
        val body = raw.copyOfRange(1 + NONCE_LEN, raw.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            SecretKeySpec(deriveKey(secret), "AES"),
            GCMParameterSpec(TAG_BITS, nonce),
        )
        cipher.updateAAD(aad(userId, vaultGeneration))
        val pt = cipher.doFinal(body)
        return String(pt, StandardCharsets.UTF_8)
    }
}
