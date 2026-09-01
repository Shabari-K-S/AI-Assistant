package com.assistant.athena.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = NeonCyan,
    onPrimary = VoidBlack,
    secondary = NeonCyanLight,
    onSecondary = VoidBlack,
    tertiary = NeonGreen,
    background = VoidBlack,
    onBackground = TextPrimary,
    surface = PanelDarkSolid,
    onSurface = TextPrimary,
    outline = PanelStroke
)

@Composable
fun AthenaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
