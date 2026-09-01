package com.assistant.athena.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.ui.theme.*
import kotlin.math.cos
import kotlin.math.sin

/**
 * JARVIS-meets-Perplexity Central Arc Reactor & Neural Core.
 * Features concentric rotating holographic rings, radiant alpha breathing pulse,
 * and crystalline geometric light rays.
 */
@Composable
fun NeuralArcReactor(
    modifier: Modifier = Modifier,
    isOnline: Boolean = true
) {
    val infiniteTransition = rememberInfiniteTransition(label = "ArcReactorTransitions")

    // Rotation 1 (Clockwise)
    val outerRotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 16000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "outerRotation"
    )

    // Rotation 2 (Counter-Clockwise)
    val innerRotation by infiniteTransition.animateFloat(
        initialValue = 360f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 10000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "innerRotation"
    )

    // Alpha breathing pulse
    val glowPulse by infiniteTransition.animateFloat(
        initialValue = 0.55f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glowPulse"
    )

    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Reactor Core Canvas
        Box(
            modifier = Modifier
                .size(140.dp)
                .padding(8.dp),
            contentAlignment = Alignment.Center
        ) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val center = Offset(size.width / 2f, size.height / 2f)
                val baseRadius = size.minDimension / 2f - 4.dp.toPx()

                // 1. Ambient Background Halo
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            NeonCyan.copy(alpha = 0.35f * glowPulse),
                            NeonCyanLight.copy(alpha = 0.12f * glowPulse),
                            Color.Transparent
                        ),
                        center = center,
                        radius = baseRadius * 1.25f
                    ),
                    radius = baseRadius * 1.25f,
                    center = center
                )

                // 2. Concentric Outer Segmented Arc Ring (Clockwise)
                val outerRadius = baseRadius * 0.95f
                val strokeOuter = 1.5.dp.toPx()
                val segments = 6
                val sweepAngle = 38f
                val gapAngle = (360f - (segments * sweepAngle)) / segments

                for (i in 0 until segments) {
                    val startAngle = outerRotation + i * (sweepAngle + gapAngle)
                    drawArc(
                        color = NeonCyan.copy(alpha = 0.8f * glowPulse),
                        startAngle = startAngle,
                        sweepAngle = sweepAngle,
                        useCenter = false,
                        topLeft = Offset(center.x - outerRadius, center.y - outerRadius),
                        size = androidx.compose.ui.geometry.Size(outerRadius * 2, outerRadius * 2),
                        style = Stroke(width = strokeOuter, cap = StrokeCap.Round)
                    )
                }

                // 3. Middle Counter-Rotating Dotted Track
                val midRadius = baseRadius * 0.72f
                val dots = 12
                for (i in 0 until dots) {
                    val angleRad = Math.toRadians((innerRotation + i * (360f / dots)).toDouble())
                    val dotX = center.x + (midRadius * cos(angleRad)).toFloat()
                    val dotY = center.y + (midRadius * sin(angleRad)).toFloat()
                    drawCircle(
                        color = if (i % 2 == 0) NeonCyan else Color.White,
                        radius = (if (i % 3 == 0) 2.2f else 1.5f) * glowPulse,
                        center = Offset(dotX, dotY)
                    )
                }

                // 4. Central Geometric 8-Point Starburst Diamond Core
                val coreRadius = baseRadius * 0.45f
                val innerR = coreRadius * 0.32f
                val path = Path()

                val numPoints = 8
                for (i in 0 until numPoints * 2) {
                    val r = if (i % 2 == 0) coreRadius else innerR
                    val angle = Math.toRadians((outerRotation * 0.5f + i * (180.0 / numPoints)).toDouble())
                    val px = center.x + (r * cos(angle)).toFloat()
                    val py = center.y + (r * sin(angle)).toFloat()
                    if (i == 0) path.moveTo(px, py) else path.lineTo(px, py)
                }
                path.close()

                // Fill crystalline core
                drawPath(
                    path = path,
                    brush = Brush.radialGradient(
                        colors = listOf(
                            Color.White,
                            NeonCyan.copy(alpha = 0.9f),
                            NeonCyanLight.copy(alpha = 0.6f)
                        ),
                        center = center,
                        radius = coreRadius
                    )
                )

                // Diamond outline
                drawPath(
                    path = path,
                    color = Color.White.copy(alpha = 0.95f),
                    style = Stroke(width = 1.2.dp.toPx())
                )

                // Bright center photon point
                drawCircle(
                    color = Color.White,
                    radius = 3.5.dp.toPx() * glowPulse,
                    center = center
                )
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Title: A.T.H.E.N.A.
        Text(
            text = "A.T.H.E.N.A.",
            color = TextPrimary,
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 6.sp,
            fontFamily = FontFamily.SansSerif
        )

        Spacer(modifier = Modifier.height(4.dp))

        // Subtitle: Monospaced Cyberpunk Telemetry
        Text(
            text = if (isOnline) "NEURAL AI HUD // SYSTEM ONLINE" else "NEURAL AI HUD // STANDBY LINK",
            color = if (isOnline) NeonCyan else NeonAmber,
            fontSize = 11.5.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 1.2.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
