package com.assistant.athena.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.cos
import kotlin.math.sin

/**
 * High-Fidelity Crystalline Starburst AI Orb (Perplexity-inspired).
 * Renders faceted iridescent geometric prisms, glowing starburst petals, and refractive lighting.
 */
class OrbView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    companion object {
        const val STATE_IDLE = 0
        const val STATE_LISTENING = 1
        const val STATE_THINKING = 2
        const val STATE_SPEAKING = 3
    }

    private var currentState = STATE_LISTENING
    private var rotationAngle = 0f
    private var pulseProgress = 1.0f
    private var audioAmplitude = 0f

    private val facetPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }
    private val edgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 1.2f
    }
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()

    private var rotationAnimator: ValueAnimator? = null
    private var pulseAnimator: ValueAnimator? = null

    init {
        setupAnimators()
    }

    private fun setupAnimators() {
        rotationAnimator = ValueAnimator.ofFloat(0f, 360f).apply {
            duration = 10000L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener {
                rotationAngle = it.animatedValue as Float
                invalidate()
            }
        }

        pulseAnimator = ValueAnimator.ofFloat(0.92f, 1.08f).apply {
            duration = 2400L
            repeatCount = ValueAnimator.INFINITE
            repeatMode = ValueAnimator.REVERSE
            addUpdateListener {
                pulseProgress = it.animatedValue as Float
                invalidate()
            }
        }
    }

    fun setState(state: Int) {
        if (currentState == state) return
        currentState = state
        when (state) {
            STATE_THINKING -> {
                rotationAnimator?.duration = 2800L
                pulseAnimator?.duration = 1000L
            }
            STATE_SPEAKING -> {
                rotationAnimator?.duration = 5000L
                pulseAnimator?.duration = 1600L
            }
            else -> {
                rotationAnimator?.duration = 10000L
                pulseAnimator?.duration = 2400L
            }
        }
        invalidate()
    }

    fun setAudioAmplitude(amp: Float) {
        audioAmplitude = amp.coerceIn(0f, 1f)
        invalidate()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        rotationAnimator?.start()
        pulseAnimator?.start()
    }

    override fun onDetachedFromWindow() {
        rotationAnimator?.cancel()
        pulseAnimator?.cancel()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val cx = width / 2f
        val cy = height / 2f
        val baseRadius = (minOf(width, height) / 2f) * 0.88f
        if (baseRadius <= 0) return

        val glassRadius = baseRadius
        val dynamicPrismRadius = baseRadius * 0.62f * (pulseProgress + (audioAmplitude * 0.12f))

        // 1. Outer Dark Glossy Glass Sphere (Perplexity Glass Orb)
        val glassPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
        val glassGradient = RadialGradient(
            cx - glassRadius * 0.15f, cy - glassRadius * 0.15f, glassRadius * 1.1f,
            intArrayOf(
                Color.argb(240, 36, 38, 46),
                Color.argb(250, 18, 19, 24),
                Color.argb(255, 8, 9, 12)
            ),
            floatArrayOf(0f, 0.6f, 1f),
            Shader.TileMode.CLAMP
        )
        glassPaint.shader = glassGradient
        canvas.drawCircle(cx, cy, glassRadius, glassPaint)

        // Delicate glass rim stroke
        val rimPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = 1.2f
            color = Color.argb(65, 255, 255, 255)
        }
        canvas.drawCircle(cx, cy, glassRadius - 0.6f, rimPaint)

        // 2. Soft Internal Refractive Core Glow
        val haloGradient = RadialGradient(
            cx, cy, dynamicPrismRadius * 1.2f,
            intArrayOf(
                Color.argb(120, 255, 255, 255),
                Color.argb(60, 56, 189, 248),
                Color.argb(25, 245, 158, 11),
                Color.TRANSPARENT
            ),
            floatArrayOf(0f, 0.45f, 0.75f, 1f),
            Shader.TileMode.CLAMP
        )
        glowPaint.shader = haloGradient
        canvas.drawCircle(cx, cy, dynamicPrismRadius * 1.2f, glowPaint)

        // 3. Faceted Crystalline Starburst (Enclosed within glass sphere)
        val numPoints = 8
        val innerRadius = dynamicPrismRadius * 0.28f
        val outerRadius = dynamicPrismRadius * 0.95f

        // Draw primary starburst cluster
        drawPrismLayer(canvas, cx, cy, numPoints, outerRadius, innerRadius, rotationAngle, 1.0f)

        // Draw secondary counter-rotating offset cluster for 3D depth
        drawPrismLayer(canvas, cx, cy, numPoints, outerRadius * 0.82f, innerRadius * 0.9f, -rotationAngle * 0.7f + 22.5f, 0.75f)

        // 4. Central Luminous Core
        val coreGradient = RadialGradient(
            cx - dynamicPrismRadius * 0.08f, cy - dynamicPrismRadius * 0.08f, dynamicPrismRadius * 0.42f,
            intArrayOf(
                Color.WHITE,
                Color.argb(230, 248, 250, 252),
                Color.argb(180, 226, 232, 240),
                Color.argb(80, 56, 189, 248),
                Color.TRANSPARENT
            ),
            floatArrayOf(0f, 0.3f, 0.6f, 0.85f, 1f),
            Shader.TileMode.CLAMP
        )
        glowPaint.shader = coreGradient
        canvas.drawCircle(cx, cy, dynamicPrismRadius * 0.38f, glowPaint)

        // 5. Specular Curved Lens Highlight on Top-Left Glass Crest (Authentic Glass Glint)
        val specPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
        val specGradient = RadialGradient(
            cx - glassRadius * 0.35f, cy - glassRadius * 0.38f, glassRadius * 0.52f,
            intArrayOf(
                Color.argb(110, 255, 255, 255),
                Color.argb(35, 255, 255, 255),
                Color.TRANSPARENT
            ),
            floatArrayOf(0f, 0.45f, 1f),
            Shader.TileMode.CLAMP
        )
        specPaint.shader = specGradient
        canvas.drawCircle(cx - glassRadius * 0.35f, cy - glassRadius * 0.38f, glassRadius * 0.52f, specPaint)
    }

    private fun drawPrismLayer(
        canvas: Canvas,
        cx: Float,
        cy: Float,
        points: Int,
        rOuter: Float,
        rInner: Float,
        angleDeg: Float,
        opacity: Float
    ) {
        val angleStep = (360.0 / points)
        for (i in 0 until points) {
            val aCenter = Math.toRadians(angleDeg + (i * angleStep))
            val aLeft = Math.toRadians(angleDeg + (i * angleStep) - (angleStep / 2.0))
            val aRight = Math.toRadians(angleDeg + (i * angleStep) + (angleStep / 2.0))

            val tipX = cx + (cos(aCenter) * rOuter).toFloat()
            val tipY = cy + (sin(aCenter) * rOuter).toFloat()

            val leftX = cx + (cos(aLeft) * rInner).toFloat()
            val leftY = cy + (sin(aLeft) * rInner).toFloat()

            val rightX = cx + (cos(aRight) * rInner).toFloat()
            val rightY = cy + (sin(aRight) * rInner).toFloat()

            // Left facet of petal
            path.reset()
            path.moveTo(cx, cy)
            path.lineTo(leftX, leftY)
            path.lineTo(tipX, tipY)
            path.close()

            val isLightFacet = (i % 2 == 0)
            val facetAlpha = if (isLightFacet) (200 * opacity).toInt() else (140 * opacity).toInt()

            facetPaint.color = when {
                currentState == STATE_THINKING -> if (isLightFacet) Color.argb(facetAlpha, 192, 132, 252) else Color.argb(facetAlpha, 251, 146, 60)
                currentState == STATE_SPEAKING -> if (isLightFacet) Color.argb(facetAlpha, 253, 224, 71) else Color.argb(facetAlpha, 52, 211, 153)
                else -> {
                    // Iridescent silver, champagne & cyan (matching Perplexity)
                    if (isLightFacet) Color.argb(facetAlpha, 241, 245, 249) // White-silver
                    else Color.argb(facetAlpha, 148, 163, 184)              // Steel-slate
                }
            }
            canvas.drawPath(path, facetPaint)

            // Right facet of petal
            path.reset()
            path.moveTo(cx, cy)
            path.lineTo(tipX, tipY)
            path.lineTo(rightX, rightY)
            path.close()

            val rightAlpha = if (isLightFacet) (150 * opacity).toInt() else (220 * opacity).toInt()
            facetPaint.color = when {
                currentState == STATE_THINKING -> Color.argb(rightAlpha, 147, 51, 234)
                currentState == STATE_SPEAKING -> Color.argb(rightAlpha, 245, 158, 11)
                else -> {
                    if (isLightFacet) Color.argb(rightAlpha, 203, 213, 225) // Pale crystal
                    else Color.argb(rightAlpha, 255, 255, 255)              // Pure white highlight
                }
            }
            canvas.drawPath(path, facetPaint)

            // Crisp facet edge lines
            edgePaint.color = Color.argb((160 * opacity).toInt(), 255, 255, 255)
            canvas.drawLine(cx, cy, tipX, tipY, edgePaint)
            canvas.drawLine(leftX, leftY, tipX, tipY, edgePaint)
            canvas.drawLine(rightX, rightY, tipX, tipY, edgePaint)
        }
    }
}
