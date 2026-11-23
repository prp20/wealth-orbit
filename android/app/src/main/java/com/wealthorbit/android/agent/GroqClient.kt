package com.wealthorbit.android.agent

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

@Serializable
data class ChatMessage(
    val role: String,
    val content: String,
)

@Serializable
data class ChatRequest(
    val model: String,
    val messages: List<ChatMessage>,
    val temperature: Double = 0.2,
)

@Serializable
data class ChatChoice(
    val message: ChatMessage,
)

@Serializable
data class ChatResponse(
    val choices: List<ChatChoice> = emptyList(),
)

class GroqClient(
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .build(),
    private val json: Json = Json { ignoreUnknownKeys = true },
    private val endpoint: String = "https://api.groq.com/openai/v1/chat/completions",
    private val model: String = "llama-3.3-70b-versatile",
) {
    fun chat(apiKey: String, messages: List<ChatMessage>): String {
        require(apiKey.isNotBlank()) { "Groq API key is required" }
        val body = json.encodeToString(
            ChatRequest(model = model, messages = messages),
        )
        val request = Request.Builder()
            .url(endpoint)
            .header("Authorization", "Bearer $apiKey")
            .header("Content-Type", "application/json")
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw IllegalStateException("Groq HTTP ${response.code}: ${raw.take(300)}")
            }
            val parsed = json.decodeFromString(ChatResponse.serializer(), raw)
            return parsed.choices.firstOrNull()?.message?.content
                ?: throw IllegalStateException("Groq returned no choices")
        }
    }

    /** Test helper: build the exact JSON body without calling the network. */
    fun requestJson(messages: List<ChatMessage>): String =
        json.encodeToString(ChatRequest(model = model, messages = messages))
}
