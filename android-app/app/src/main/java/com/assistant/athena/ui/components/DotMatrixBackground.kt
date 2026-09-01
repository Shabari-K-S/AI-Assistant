package com.assistant.athena.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.assistant.athena.ui.theme.DotGridColor
import com.assistant.athena.ui.theme.VoidBlack

/**
 * High-performance 120Hz 2D dot-grid overlay canvas.
 * Renders subtle cybernetic HUD matrix dots spaced 24.dp apart on deep void black.
 */
@Composable
fun DotMatrixBackground(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier
            .fillMaxSize()
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            drawRect(color = VoidBlack)

            val spacingPx = 24.dp.toPx()
            val dotRadius = 1.25.dp.toPx()

            var x = spacingPx / 2f
            while (x < size.width) {
                var y = spacingPx / 2f
                while (y < size.height) {
                    drawCircle(
                        color = DotGridColor,
                        radius = dotRadius,
                        center = Offset(x, y)
                    )
                    y += spacingPx
                }
                x += spacingPx
            }
        }

        content()
    }
}
