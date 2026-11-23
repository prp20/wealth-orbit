package com.wealthorbit.android.agent

import org.junit.Assert.assertTrue
import org.junit.Test

class GroqClientTest {
    @Test
    fun requestJson_includesMessagesAndModel() {
        val client = GroqClient()
        val body = client.requestJson(
            listOf(
                ChatMessage(role = "system", content = "be brief"),
                ChatMessage(role = "user", content = "hello"),
            ),
        )
        assertTrue(body.contains("\"model\""))
        assertTrue(body.contains("llama-3.3-70b-versatile"))
        assertTrue(body.contains("\"role\":\"system\""))
        assertTrue(body.contains("\"content\":\"be brief\""))
        assertTrue(body.contains("\"role\":\"user\""))
        assertTrue(body.contains("\"content\":\"hello\""))
    }
}
