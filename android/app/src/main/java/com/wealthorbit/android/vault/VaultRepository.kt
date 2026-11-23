package com.wealthorbit.android.vault

import com.wealthorbit.android.db.AppConfig
import com.wealthorbit.android.db.PostgresPooler
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

data class VaultRow(
    val userId: String,
    val vaultGeneration: Int,
    val version: Int,
    val ciphertext: String,
    val updatedAt: Instant?,
)

data class HoldingView(
    val assetName: String,
    val quantity: String,
    val investedAmount: String,
)

data class DecryptedPortfolio(
    val vaultGeneration: Int,
    val version: Int,
    val holdings: List<HoldingView>,
    val assetCount: Int,
    val transactionCount: Int,
)

class VaultConflictException(message: String) : Exception(message)

class VaultRepository {
    fun fetchRow(config: AppConfig): VaultRow? {
        PostgresPooler.open(config.poolerUrl).use { conn ->
            conn.prepareStatement(
                """
                SELECT user_id, vault_generation, version, ciphertext, updated_at
                FROM public.portfolio_vault
                WHERE user_id = ?::uuid
                """.trimIndent(),
            ).use { stmt ->
                stmt.setObject(1, UUID.fromString(config.vaultUserId))
                stmt.executeQuery().use { rs ->
                    if (!rs.next()) return null
                    return VaultRow(
                        userId = rs.getObject("user_id").toString(),
                        vaultGeneration = rs.getInt("vault_generation"),
                        version = rs.getInt("version"),
                        ciphertext = rs.getString("ciphertext"),
                        updatedAt = rs.getTimestamp("updated_at")?.toInstant(),
                    )
                }
            }
        }
    }

    fun loadDecrypted(config: AppConfig): DecryptedPortfolio? {
        val row = fetchRow(config) ?: return null
        val json = VaultCrypto.decryptSnapshot(
            row.ciphertext,
            secret = config.encryptionSecret,
            userId = config.vaultUserId,
            vaultGeneration = row.vaultGeneration,
        )
        val root = JSONObject(json)
        val assets = root.optJSONArray("assets") ?: JSONArray()
        val nameById = mutableMapOf<String, String>()
        for (i in 0 until assets.length()) {
            val a = assets.getJSONObject(i)
            nameById[a.getString("asset_id")] = a.optString("asset_name", a.optString("external_id"))
        }
        val holdingsJson = root.optJSONArray("holdings") ?: JSONArray()
        val holdings = buildList {
            for (i in 0 until holdingsJson.length()) {
                val h = holdingsJson.getJSONObject(i)
                val assetId = h.getString("asset_id")
                add(
                    HoldingView(
                        assetName = nameById[assetId] ?: assetId,
                        quantity = h.optString("current_quantity", "0"),
                        investedAmount = h.optString("invested_amount", "0"),
                    ),
                )
            }
        }
        val tx = root.optJSONArray("transactions") ?: JSONArray()
        return DecryptedPortfolio(
            vaultGeneration = row.vaultGeneration,
            version = row.version,
            holdings = holdings,
            assetCount = assets.length(),
            transactionCount = tx.length(),
        )
    }

    /**
     * Optimistic put: client sends expected current [expectedVersion];
     * server row must match, then version becomes expectedVersion+1.
     */
    fun putCiphertext(
        config: AppConfig,
        expectedVersion: Int,
        ciphertext: String,
        vaultGeneration: Int,
    ): Int {
        PostgresPooler.open(config.poolerUrl).use { conn ->
            conn.autoCommit = false
            try {
                val user = UUID.fromString(config.vaultUserId)
                conn.prepareStatement(
                    "SELECT version FROM public.portfolio_vault WHERE user_id = ?::uuid FOR UPDATE",
                ).use { stmt ->
                    stmt.setObject(1, user)
                    stmt.executeQuery().use { rs ->
                        if (!rs.next()) {
                            if (expectedVersion != 0) {
                                throw VaultConflictException("vault missing; expected version $expectedVersion")
                            }
                            conn.prepareStatement(
                                """
                                INSERT INTO public.portfolio_vault
                                  (user_id, vault_generation, version, ciphertext, updated_at)
                                VALUES (?::uuid, ?, 1, ?, NOW())
                                """.trimIndent(),
                            ).use { insert ->
                                insert.setObject(1, user)
                                insert.setInt(2, vaultGeneration)
                                insert.setString(3, ciphertext)
                                insert.executeUpdate()
                            }
                            conn.commit()
                            return 1
                        }
                        val current = rs.getInt("version")
                        if (current != expectedVersion) {
                            throw VaultConflictException(
                                "stale version: current=$current expected=$expectedVersion",
                            )
                        }
                    }
                }
                val next = expectedVersion + 1
                conn.prepareStatement(
                    """
                    UPDATE public.portfolio_vault
                    SET version = ?, ciphertext = ?, updated_at = NOW()
                    WHERE user_id = ?::uuid AND version = ?
                    """.trimIndent(),
                ).use { upd ->
                    upd.setInt(1, next)
                    upd.setString(2, ciphertext)
                    upd.setObject(3, user)
                    upd.setInt(4, expectedVersion)
                    val n = upd.executeUpdate()
                    if (n != 1) {
                        throw VaultConflictException("concurrent update")
                    }
                }
                conn.commit()
                return next
            } catch (e: Exception) {
                conn.rollback()
                throw e
            }
        }
    }
}
