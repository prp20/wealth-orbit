package com.wealthorbit.android.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.wealthorbit.android.db.PoolerConfigStore
import com.wealthorbit.android.market.IndexQuote
import com.wealthorbit.android.market.MarketRepository
import com.wealthorbit.android.market.StockQuote
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun HomeScreen() {
    val context = LocalContext.current
    val store = remember { PoolerConfigStore(context) }
    val repo = remember { MarketRepository() }
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var indexes by remember { mutableStateOf<List<IndexQuote>>(emptyList()) }
    var stocks by remember { mutableStateOf<List<StockQuote>>(emptyList()) }

    fun refresh() {
        scope.launch {
            loading = true
            error = null
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    if (!store.isConfigured()) {
                        throw IllegalStateException("Complete setup first")
                    }
                    val cfg = store.load()
                    val idx = repo.latestIndexes(cfg, limit = 5)
                    val quotes = repo.latestStockQuotes(
                        cfg,
                        listOf("RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"),
                    )
                    idx to quotes
                }
            }
            loading = false
            result.fold(
                onSuccess = { (idx, quotes) ->
                    indexes = idx
                    stocks = quotes
                },
                onFailure = {
                    error = it.message ?: "Market load failed"
                    indexes = emptyList()
                    stocks = emptyList()
                },
            )
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Market", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Read-only indexes and a small watchlist. No sync jobs run on device.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Button(onClick = { refresh() }, modifier = Modifier.fillMaxWidth()) {
            Text("Refresh")
        }
        when {
            loading -> CircularProgressIndicator()
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            else -> {
                Text("Indexes", style = MaterialTheme.typography.titleMedium)
                LazyColumn(
                    modifier = Modifier.weight(1f, fill = false),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(indexes) { row ->
                        Text(
                            "${row.code}: ${row.close ?: "—"} (${row.asOf ?: "n/a"})",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                Text("Watchlist", style = MaterialTheme.typography.titleMedium)
                LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(stocks) { row ->
                        Text(
                            "${row.symbol}: ${row.close ?: "—"} (${row.asOf ?: "n/a"})",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}
