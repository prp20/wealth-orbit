package com.wealthorbit.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF1B4D3E),
    onPrimary = Color(0xFFF5F7F4),
    secondary = Color(0xFF3D6B5A),
    background = Color(0xFFF3F1EC),
    surface = Color(0xFFF8F6F1),
    onBackground = Color(0xFF1A1F1C),
    onSurface = Color(0xFF1A1F1C),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF8FCBB3),
    onPrimary = Color(0xFF0C241C),
    secondary = Color(0xFFA3C4B5),
    background = Color(0xFF121612),
    surface = Color(0xFF1A201C),
    onBackground = Color(0xFFE8EEE9),
    onSurface = Color(0xFFE8EEE9),
)

@Composable
fun WealthOrbitTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
