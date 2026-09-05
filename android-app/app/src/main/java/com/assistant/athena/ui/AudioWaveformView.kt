package com.assistant.athena.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

/**
 * Dynamic Audio Waveform Visualizer (Perplexity-inspired).
 * Renders horizontal glowing dot-matrix frequency spectrum reacting live to speech & audio energy.
 */
class AudioWaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    private val numColumns = 36
    private val maxDotsPerCol = 5
    private val columnHeights = FloatArray(numColumns) { 0.3f }
    private val targetHeights = FloatArray(numColumns) { 0.3f }

    private var animTime = 0.0
    private var isListening = true
    private var isThinking = false
    private var isSpeaking = false
    private var micLevel = 0f

    private var idleAnimator: ValueAnimator? = null

    init {
        setupAnimator()
    }

    private fun setupAnimator() {
        idleAnimator = ValueAnimator.ofFloat(0f, 1000f).apply {
            duration = 24000L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener {
                animTime = (it.animatedValue as Float).toDouble() * 0.15
                updatePhysics()
                invalidate()
            }
        }
    }

    fun setMicLevel(level: Float) {
        micLevel = level.coerceIn(0f, 1f)
        val center = numColumns / 2f
        if (micLevel > 0.04f) {
            // User is actively speaking -> dynamically elevate columns with voice energy
            for (i in 0 until numColumns) {
                val dist = abs(i - center) / center
                val bell = (1f - (dist * 0.65f)).coerceIn(0.2f, 1.0f)
                val noise = (Random.nextFloat() - 0.5f) * 0.2f
                targetHeights[i] = (0.25f + ((micLevel * 1.1f + noise) * bell * 0.75f)).coerceIn(0.2f, 1.0f)
            }
        } else {
            // Organic resting baseline audio curve (Perplexity multi-dot equalizer contour)
            for (i in 0 until numColumns) {
                val dist = abs(i - center) / center
                val bell = (1f - (dist * 0.85f)).coerceIn(0.12f, 1.0f)
                val wave = (sin(animTime * 0.3 + (i * 0.26)).toFloat() * 0.07f)
                targetHeights[i] = (0.16f + (bell * 0.48f) + wave).coerceIn(0.15f, 0.72f)
            }
        }
    }

    fun setMode(listening: Boolean, thinking: Boolean, speaking: Boolean) {
        isListening = listening
        isThinking = thinking
        isSpeaking = speaking
    }

    private fun updatePhysics() {
        val center = numColumns / 2f
        for (i in 0 until numColumns) {
            if (isThinking) {
                // Traveling wave during thinking
                val wave = (sin(animTime * 0.8 + (i * 0.3)) * 0.4 + 0.45).toFloat()
                targetHeights[i] = (0.2f + wave * 0.65f).coerceIn(0.15f, 0.95f)
            } else if (isSpeaking) {
                // Rhythmic voice wave during speaking
                val wave1 = sin(animTime * 0.65 + (i * 0.24)).toFloat()
                val wave2 = cos(animTime * 0.95 + (i * 0.16)).toFloat()
                val dist = abs(i - center) / center
                val bell = (1f - (dist * 0.6f)).coerceIn(0.25f, 1.0f)
                val combined = (((wave1 + wave2) * 0.28f + 0.52f) * bell).coerceIn(0.2f, 0.9f)
                targetHeights[i] = combined
            } else if (micLevel <= 0.04f) {
                // Organic resting baseline audio contour
                val dist = abs(i - center) / center
                val bell = (1f - (dist * 0.85f)).coerceIn(0.12f, 1.0f)
                val wave = (sin(animTime * 0.3 + (i * 0.26)).toFloat() * 0.07f)
                targetHeights[i] = (0.16f + (bell * 0.48f) + wave).coerceIn(0.15f, 0.72f)
            }
            // Smooth natural spring dampening
            columnHeights[i] += (targetHeights[i] - columnHeights[i]) * 0.32f
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        idleAnimator?.start()
    }

    override fun onDetachedFromWindow() {
        idleAnimator?.cancel()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return

        val paddingH = width * 0.04f
        val usableWidth = width - (paddingH * 2)
        val colSpacing = usableWidth / numColumns
        val dotRadius = (colSpacing * 0.24f).coerceIn(2.0f, 3.4f)
        val dotGap = dotRadius * 2.6f
        val centerY = height / 2f

        for (col in 0 until numColumns) {
            val colX = paddingH + (col * colSpacing) + (colSpacing / 2f)
            val heightRatio = columnHeights[col].coerceIn(0.12f, 1f)
            val activeDots = (heightRatio * maxDotsPerCol).toInt().coerceIn(1, maxDotsPerCol)

            for (row in 0 until activeDots) {
                val yOffset = (row * dotGap)
                val intensity = row.toFloat() / maxDotsPerCol.toFloat()
                val dotColor = when {
                    isThinking -> {
                        val r = (168 + (80 * intensity)).toInt().coerceIn(0, 255)
                        val g = (85 + (100 * intensity)).toInt().coerceIn(0, 255)
                        val b = 247
                        Color.rgb(r, g, b)
                    }
                    isSpeaking -> {
                        val r = 251
                        val g = (191 - (50 * intensity)).toInt().coerceIn(0, 255)
                        val b = (36 + (80 * intensity)).toInt().coerceIn(0, 255)
                        Color.rgb(r, g, b)
                    }
                    else -> {
                        // Perplexity Warm Amber/Copper Glow (#E28743 to #FB923C)
                        val r = (240 + (15 * intensity)).toInt().coerceIn(0, 255)
                        val g = (130 + (45 * intensity)).toInt().coerceIn(0, 255)
                        val b = (50 + (30 * intensity)).toInt().coerceIn(0, 255)
                        Color.rgb(r, g, b)
                    }
                }

                dotPaint.color = dotColor
                dotPaint.alpha = (175 + (80 * intensity)).toInt().coerceIn(0, 255)

                // Top half dots
                val dotYTop = centerY - yOffset
                canvas.drawCircle(colX, dotYTop, dotRadius, dotPaint)

                // Bottom half mirrored dots
                if (row > 0) {
                    val dotYBottom = centerY + yOffset
                    canvas.drawCircle(colX, dotYBottom, dotRadius, dotPaint)
                }

                // Peak bright highlight on top dot
                if (row == activeDots - 1 && intensity > 0.45f) {
                    glowPaint.color = Color.WHITE
                    glowPaint.alpha = 140
                    canvas.drawCircle(colX, dotYTop, dotRadius * 0.5f, glowPaint)
                    if (row > 0) {
                        canvas.drawCircle(colX, centerY + yOffset, dotRadius * 0.5f, glowPaint)
                    }
                }
            }
        }
    }
}
