package com.assistant.athena.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.BackendStatus
import com.assistant.athena.R
import com.assistant.athena.ui.theme.*
import kotlinx.coroutines.delay

/**
 * Tactical Cyberpunk-Minimalist Splash Screen for ATHENA.
 * Showcases the Athena emblem framed in glowing holographic telemetry rings,
 * dynamic neural initialization telemetry, and smooth exit transition.
 */
@Composable
fun AthenaSplashScreen(
    status: BackendStatus,
    onFinished: () -> Unit,
    modifier: Modifier = Modifier
) {
    var isExiting by remember { mutableStateOf(false) }

    // Auto-advance after smooth initialization sequence
    LaunchedEffect(Unit) {
        delay(1600) // Optimal duration for brand impression without hindering productivity
        isExiting = true
        delay(350) // Allow exit animation to complete
        onFinished()
    }

    // Infinite rotations and breathing pulse for cybernetic emblem frame
    val infiniteTransition = rememberInfiniteTransition(label = "SplashTelemetry")

    val outerRotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 14000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "outerRingRotation"
    )

    val innerRotation by infiniteTransition.animateFloat(
        initialValue = 360f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 9000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "innerRingRotation"
    )

    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.98f,
        targetValue = 1.02f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "emblemPulse"
    )

    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.15f,
        targetValue = 0.35f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glowPulse"
    )

    AnimatedVisibility(
        visible = !isExiting,
        enter = fadeIn(tween(300)) + scaleIn(initialScale = 0.95f),
        exit = fadeOut(tween(350)) + scaleOut(targetScale = 1.05f)
    ) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Color(0xFF161922),
                            Color(0xFF0C0E14),
                            Color(0xFF060709)
                        ),
                        radius = 1200f
                    )
                )
                .clickable(
                    indication = null,
                    interactionSource = remember { MutableInteractionSource() }
                ) {
                    isExiting = true
                    onFinished()
                },
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp)
            ) {
                Spacer(modifier = Modifier.weight(1f))

                // Center Emblem & Holographic Telemetry Rings
                Box(
                    modifier = Modifier
                        .size(240.dp)
                        .scale(pulseScale),
                    contentAlignment = Alignment.Center
                ) {
                    // Ambient radial glow behind emblem
                    Canvas(modifier = Modifier.fillMaxSize()) {
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    Color(0xFF20B2AA).copy(alpha = glowAlpha),
                                    Color(0xFF00E5FF).copy(alpha = glowAlpha * 0.4f),
                                    Color.Transparent
                                )
                            ),
                            radius = size.minDimension / 2.0f
                        )
                    }

                    // Rotating Holographic Telemetry Rings
                    Canvas(
                        modifier = Modifier
                            .fillMaxSize()
                            .rotate(outerRotation)
                    ) {
                        val strokeWidth = 1.5.dp.toPx()
                        val radius = size.minDimension / 2.0f - 8.dp.toPx()

                        // Segmented outer ring
                        drawArc(
                            color = Color(0xFF20B2AA).copy(alpha = 0.6f),
                            startAngle = 0f,
                            sweepAngle = 70f,
                            useCenter = false,
                            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
                        )
                        drawArc(
                            color = Color(0xFFFFFFFF).copy(alpha = 0.3f),
                            startAngle = 90f,
                            sweepAngle = 45f,
                            useCenter = false,
                            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
                        )
                        drawArc(
                            color = Color(0xFF20B2AA).copy(alpha = 0.6f),
                            startAngle = 180f,
                            sweepAngle = 70f,
                            useCenter = false,
                            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
                        )
                        drawArc(
                            color = Color(0xFFFFFFFF).copy(alpha = 0.3f),
                            startAngle = 270f,
                            sweepAngle = 45f,
                            useCenter = false,
                            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
                        )
                    }

                    // Counter-rotating inner technical ring
                    Canvas(
                        modifier = Modifier
                            .fillMaxSize()
                            .rotate(innerRotation)
                    ) {
                        val strokeWidth = 1.dp.toPx()
                        val radius = size.minDimension / 2.0f - 20.dp.toPx()

                        drawCircle(
                            color = Color(0xFF2B2B2B),
                            radius = radius,
                            style = Stroke(width = strokeWidth)
                        )

                        // Precision tick marks
                        for (i in 0 until 12) {
                            val angle = (i * 30) * (Math.PI / 180.0)
                            val startX = (center.x + (radius - 5.dp.toPx()) * kotlin.math.cos(angle)).toFloat()
                            val startY = (center.y + (radius - 5.dp.toPx()) * kotlin.math.sin(angle)).toFloat()
                            val endX = (center.x + (radius + 2.dp.toPx()) * kotlin.math.cos(angle)).toFloat()
                            val endY = (center.y + (radius + 2.dp.toPx()) * kotlin.math.sin(angle)).toFloat()

                            drawLine(
                                color = if (i % 3 == 0) Color(0xFF20B2AA).copy(alpha = 0.8f) else Color(0xFF555555),
                                start = Offset(startX, startY),
                                end = Offset(endX, endY),
                                strokeWidth = 1.dp.toPx()
                            )
                        }
                    }

                    // Athena Emblem
                    Box(
                        modifier = Modifier
                            .size(160.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF000000)),
                        contentAlignment = Alignment.Center
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_splash_logo),
                            contentDescription = "ATHENA Neural Core",
                            contentScale = ContentScale.Fit,
                            modifier = Modifier
                                .fillMaxSize()
                                .clip(CircleShape)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(28.dp))

                // Brand Moniker
                Text(
                    text = "A T H E N A",
                    color = Color.White,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 6.sp,
                    fontFamily = FontFamily.SansSerif
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = "NEURAL COGNITIVE INTELLIGENCE",
                    color = Color(0xFF20B2AA),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium,
                    letterSpacing = 2.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.weight(1f))

                // Initialization Telemetry & Progress
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    val statusText = when {
                        status.isOnline -> "SYSTEM ONLINE • READY"
                        status.phase.isNotBlank() -> status.phase.uppercase()
                        else -> "INITIALIZING NEURAL CORE..."
                    }

                    Text(
                        text = statusText,
                        color = Color(0xFFA1A1AA),
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 1.sp
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Minimalist glowing pulse line
                    Box(
                        modifier = Modifier
                            .width(140.dp)
                            .height(2.dp)
                            .clip(RoundedCornerShape(1.dp))
                            .background(Color(0xFF1E1E1E))
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxHeight()
                                .fillMaxWidth(fraction = pulseScale - 0.5f)
                                .background(
                                    Brush.horizontalGradient(
                                        colors = listOf(
                                            Color(0xFF20B2AA).copy(alpha = 0.2f),
                                            Color(0xFF20B2AA),
                                            Color(0xFFFFFFFF)
                                        )
                                    )
                                )
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "TAP TO CONTINUE",
                        color = Color(0xFF52525B),
                        fontSize = 9.sp,
                        letterSpacing = 1.5.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}
