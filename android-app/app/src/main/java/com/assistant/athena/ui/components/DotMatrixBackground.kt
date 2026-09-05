package com.assistant.athena.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import com.assistant.athena.ui.theme.NeonCyan
import com.assistant.athena.ui.theme.VoidBlack

/**
 * Modern Perplexity-Style Obsidian Matte Canvas with subtle ambient atmospheric lighting.
 */
@Composable
fun DotMatrixBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier.fillMaxSize()
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            // Base Matte Obsidian Dark
            drawRect(color = VoidBlack)

            // Soft atmospheric radial illumination at top
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        NeonCyan.copy(alpha = 0.055f),
                        Color.Transparent
                    ),
                    center = Offset(size.width / 2f, size.height * 0.15f),
                    radius = size.width * 0.85f
                ),
                radius = size.width * 0.85f,
                center = Offset(size.width / 2f, size.height * 0.15f)
            )
        }

        content()
    }
}
