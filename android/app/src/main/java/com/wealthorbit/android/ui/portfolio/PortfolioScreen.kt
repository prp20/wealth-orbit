package com.wealthorbit.android.ui.portfolio

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
import com.wealthorbit.android.vault.DecryptedPortfolio
import com.wealthorbit.android.vault.VaultRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun PortfolioScreen() {
    val context = LocalContext.current
    val store = remember { PoolerConfigStore(context) }
    val repo = remember { VaultRepository() }
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var portfolio by remember { mutableStateOf<DecryptedPortfolio?>(null) }

    fun refresh() {
        scope.launch {
            loading = true
            error = null
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    if (!store.isConfigured()) {
                        throw IllegalStateException("Complete setup first")
                    }
                    repo.loadDecrypted(store.load())
                }
            }
            loading = false
            result.fold(
                onSuccess = {
                    portfolio = it
                    if (it == null) error = "No vault row for this user"
                },
                onFailure = {
                    error = it.message ?: "Failed to load vault"
                    portfolio = null
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
        Text("Portfolio", style = MaterialTheme.typography.headlineSmall)
        Button(onClick = { refresh() }, modifier = Modifier.fillMaxWidth()) {
            Text("Refresh vault")
        }
        when {
            loading -> CircularProgressIndicator()
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.error)
            portfolio != null -> {
                val p = portfolio!!
                Text(
                    "gen=${p.vaultGeneration} version=${p.version} · " +
                        "${p.assetCount} assets · ${p.transactionCount} tx · ${p.holdings.size} holdings",
                    style = MaterialTheme.typography.bodySmall,
                )
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(p.holdings) { h ->
                        Text(
                            "${h.assetName}: qty ${h.quantity}, invested ${h.investedAmount}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}
