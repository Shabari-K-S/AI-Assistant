package com.assistant.athena.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.assistant.athena.ui.theme.PerplexityPillBorder
import com.assistant.athena.ui.theme.PerplexitySurfaceElevated

/**
 * Authentic Perplexity Elevated Surface Card container.
 * Features 16.dp rounded corners, elevated obsidian surface (#1F2633),
 * and subtle slate border stroke (#2E3848).
 */
@Composable
fun HudCard(
    modifier: Modifier = Modifier,
    cornerRadius: Dp = 16.dp,
    borderColor: Color = PerplexityPillBorder,
    backgroundColor: Color = PerplexitySurfaceElevated,
    content: @Composable ColumnScope.() -> Unit
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(cornerRadius))
            .border(
                border = BorderStroke(1.dp, borderColor),
                shape = RoundedCornerShape(cornerRadius)
            ),
        color = backgroundColor,
        shape = RoundedCornerShape(cornerRadius)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            content = content
        )
    }
}
