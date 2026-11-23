package com.wealthorbit.android.market

import com.wealthorbit.android.db.AppConfig
import com.wealthorbit.android.db.PostgresPooler
import java.math.BigDecimal

data class IndexQuote(
    val code: String,
    val name: String,
    val close: BigDecimal?,
    val asOf: String?,
)

data class StockQuote(
    val symbol: String,
    val close: BigDecimal?,
    val asOf: String?,
)

class MarketRepository {
    fun latestIndexes(config: AppConfig, limit: Int = 5): List<IndexQuote> {
        PostgresPooler.open(config.poolerUrl).use { conn ->
            conn.prepareStatement(
                """
                SELECT i.index_code,
                       i.index_name,
                       h.close,
                       h.history_date::text AS as_of
                FROM market_data.index_reference i
                JOIN LATERAL (
                  SELECT close, history_date
                  FROM market_data.index_daily_history d
                  WHERE d.index_id = i.index_id
                  ORDER BY d.history_date DESC
                  LIMIT 1
                ) h ON TRUE
                WHERE i.is_active = TRUE
                ORDER BY i.index_code
                LIMIT ?
                """.trimIndent(),
            ).use { stmt ->
                stmt.setInt(1, limit)
                stmt.executeQuery().use { rs ->
                    val rows = mutableListOf<IndexQuote>()
                    while (rs.next()) {
                        rows += IndexQuote(
                            code = rs.getString("index_code"),
                            name = rs.getString("index_name") ?: rs.getString("index_code"),
                            close = rs.getBigDecimal("close"),
                            asOf = rs.getString("as_of"),
                        )
                    }
                    return rows
                }
            }
        }
    }

    fun latestStockQuotes(config: AppConfig, symbols: List<String>): List<StockQuote> {
        if (symbols.isEmpty()) return emptyList()
        PostgresPooler.open(config.poolerUrl).use { conn ->
            conn.prepareStatement(
                """
                SELECT s.trading_symbol,
                       p.close,
                       p.trading_date::text AS as_of
                FROM market_data.stock_reference s
                JOIN LATERAL (
                  SELECT close, trading_date
                  FROM market_data.stock_daily_prices d
                  WHERE d.stock_id = s.stock_id
                  ORDER BY d.trading_date DESC
                  LIMIT 1
                ) p ON TRUE
                WHERE s.is_active = TRUE
                  AND s.trading_symbol = ANY (?)
                ORDER BY s.trading_symbol
                """.trimIndent(),
            ).use { stmt ->
                val arr = conn.createArrayOf("text", symbols.toTypedArray())
                stmt.setArray(1, arr)
                stmt.executeQuery().use { rs ->
                    val rows = mutableListOf<StockQuote>()
                    while (rs.next()) {
                        rows += StockQuote(
                            symbol = rs.getString("trading_symbol"),
                            close = rs.getBigDecimal("close"),
                            asOf = rs.getString("as_of"),
                        )
                    }
                    return rows
                }
            }
        }
    }
}
