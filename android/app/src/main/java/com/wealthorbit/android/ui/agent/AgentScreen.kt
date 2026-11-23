package com.wealthorbit.android.ui.agent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.wealthorbit.android.agent.ChatMessage
import com.wealthorbit.android.agent.GroqClient
import com.wealthorbit.android.agent.SkillLoader
import com.wealthorbit.android.db.PoolerConfigStore
import com.wealthorbit.android.vault.VaultRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun AgentScreen() {
    val context = LocalContext.current
    val store = remember { PoolerConfigStore(context) }
    val vaultRepo = remember { VaultRepository() }
    val groq = remember { GroqClient() }
    val scope = rememberCoroutineScope()

    var question by remember { mutableStateOf("") }
    var answer by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Agent", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Disclosure: when you ask a question, a summary of your decrypted portfolio " +
                "and the local skill.md are sent to Groq over HTTPS. Wealth Orbit does not " +
                "give personalized investment advice.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.secondary,
        )
        OutlinedTextField(
            value = question,
            onValueChange = { question = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Your question") },
            minLines = 3,
        )
        Button(
            enabled = !loading && question.isNotBlank(),
            onClick = {
                scope.launch {
                    loading = true
                    error = null
                    answer = null
                    val result = withContext(Dispatchers.IO) {
                        runCatching {
                            val cfg = store.load()
                            if (cfg.groqApiKey.isBlank()) {
                                throw IllegalStateException("Add a Groq API key in Setup")
                            }
                            val skill = SkillLoader.load(context)
                            val portfolio = if (store.isConfigured()) {
                                vaultRepo.loadDecrypted(cfg)
                            } else {
                                null
                            }
                            val holdingsSummary = portfolio?.holdings
                                ?.take(40)
                                ?.joinToString("\n") { "- ${it.assetName}: qty ${it.quantity}, invested ${it.investedAmount}" }
                                ?: "(no vault holdings loaded)"
                            val system = buildString {
                                appendLine(skill)
                                appendLine()
                                appendLine("Portfolio snapshot (on-device decrypt; do not invent extras):")
                                appendLine(holdingsSummary)
                            }
                            groq.chat(
                                cfg.groqApiKey,
                                listOf(
                                    ChatMessage(role = "system", content = system),
                                    ChatMessage(role = "user", content = question.trim()),
                                ),
                            )
                        }
                    }
                    loading = false
                    result.fold(
                        onSuccess = { answer = it },
                        onFailure = { error = it.message ?: "Agent failed" },
                    )
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (loading) "Asking Groq…" else "Ask")
        }
        if (loading) CircularProgressIndicator()
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        answer?.let {
            Text("Answer", style = MaterialTheme.typography.titleMedium)
            Text(it, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
