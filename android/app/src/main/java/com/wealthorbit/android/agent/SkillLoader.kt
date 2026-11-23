package com.wealthorbit.android.agent

import android.content.Context
import java.io.File

object SkillLoader {
    private const val FILE_NAME = "skill.md"

    val DEFAULT_SKILL = """
You are a read-only assistant for Wealth Orbit.
Use only the portfolio and market facts provided in the prompt.
Do not invent holdings. Do not give personalized investment advice.
If data is missing, say so.
""".trimIndent()

    fun load(context: Context): String {
        val file = File(context.filesDir, FILE_NAME)
        if (file.isFile && file.length() > 0L) {
            return file.readText()
        }
        return runCatching {
            context.assets.open("skill.md.example").bufferedReader().use { it.readText() }
        }.getOrDefault(DEFAULT_SKILL)
    }

    fun importSkill(context: Context, markdown: String) {
        File(context.filesDir, FILE_NAME).writeText(markdown)
    }
}
