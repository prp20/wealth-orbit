package com.wealthorbit.android.ui.agent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun AgentScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Agent", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Groq Q&A with a local skill.md will live here (Task 14). " +
                "Portfolio context is sent to Groq only when you ask.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
