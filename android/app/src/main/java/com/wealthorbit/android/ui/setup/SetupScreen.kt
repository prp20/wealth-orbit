package com.wealthorbit.android.ui.setup

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun SetupScreen(onConfigured: () -> Unit) {
    var poolerUrl by remember { mutableStateOf("") }
    var secret by remember { mutableStateOf("") }
    var vaultUserId by remember { mutableStateOf("") }
    var groqKey by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Wealth Orbit", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Paste the restricted session pooler URL (market read-only role), " +
                "encryption secret, and vault user id. Never use the PC postgres superuser URL.",
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedTextField(
            value = poolerUrl,
            onValueChange = { poolerUrl = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Restricted pooler URL") },
            singleLine = true,
        )
        OutlinedTextField(
            value = secret,
            onValueChange = { secret = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Portfolio encryption secret") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
        )
        OutlinedTextField(
            value = vaultUserId,
            onValueChange = { vaultUserId = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("VAULT_USER_ID") },
            singleLine = true,
        )
        OutlinedTextField(
            value = groqKey,
            onValueChange = { groqKey = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Groq API key (optional)") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
        )
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Button(
            onClick = {
                error = when {
                    poolerUrl.isBlank() -> "Pooler URL is required"
                    secret.isBlank() -> "Encryption secret is required"
                    vaultUserId.isBlank() -> "VAULT_USER_ID is required"
                    else -> null
                }
                if (error == null) {
                    // Persistence wired in Task 12 (EncryptedSharedPreferences).
                    onConfigured()
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Continue")
        }
    }
}
