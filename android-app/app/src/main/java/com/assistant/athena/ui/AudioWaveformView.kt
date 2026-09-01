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

    private val numColumns = 40
    private val maxDotsPerCol = 9
    private val columnHeights = FloatArray(numColumns) { 0.1f }
    private val targetHeights = FloatArray(numColumns) { 0.1f }

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
            duration = 30000L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener {
                animTime = (it.animatedValue as Float).toDouble() * 0.1
                updatePhysics()
                invalidate()
            }
        }
    }

    fun setMicLevel(level: Float) {
        micLevel = level.coerceIn(0f, 1f)
        val center = numColumns / 2
        if (micLevel > 0.06f) {
            // User is actively speaking -> dynamically elevate columns
            for (i in 0 until numColumns) {
                val dist = abs(i - center).toFloat() / center.toFloat()
                val falloff = (1f - (dist * 0.65f)).coerceAtLeast(0.15f)
                val noise = (Random.nextFloat() - 0.5f) * 0.25f
                targetHeights[i] = ((micLevel * 0.9f + noise) * falloff).coerceIn(0.12f, 1.0f)
            }
        } else {
            // Silence / calm baseline
            for (i in 0 until numColumns) {
                val dist = abs(i - center).toFloat() / center.toFloat()
                val wave = (sin(animTime * 0.2 + (i * 0.2)).toFloat() * 0.04f)
                val centerWeight = (1f - (dist * 0.4f)) * 0.1f
                targetHeights[i] = (centerWeight + wave).coerceIn(0.06f, 0.18f)
            }
        }
    }

    fun setMode(listening: Boolean, thinking: Boolean, speaking: Boolean) {
        isListening = listening
        isThinking = thinking
        isSpeaking = speaking
    }

    private fun updatePhysics() {
        val center = numColumns / 2
        for (i in 0 until numColumns) {
            if (isThinking) {
                // Traveling wave during thinking
                val wave = (sin(animTime * 0.7 + (i * 0.28)) * 0.45 + 0.45).toFloat()
                targetHeights[i] = (0.15f + wave * 0.55f).coerceIn(0.1f, 0.85f)
            } else if (isSpeaking) {
                // Rhythmic voice wave during speaking
                val wave1 = sin(animTime * 0.55 + (i * 0.22)).toFloat()
                val wave2 = cos(animTime * 0.85 + (i * 0.14)).toFloat()
                val combined = ((wave1 + wave2) * 0.25f + 0.45f).coerceIn(0.12f, 0.8f)
                targetHeights[i] = combined
            } else if (micLevel <= 0.06f) {
                // Calm resting baseline dots
                val dist = abs(i - center).toFloat() / center.toFloat()
                val wave = (sin(animTime * 0.2 + (i * 0.2)).toFloat() * 0.03f)
                val centerWeight = (1f - (dist * 0.4f)) * 0.09f
                targetHeights[i] = (centerWeight + wave).coerceIn(0.05f, 0.15f)
            }
            // Smooth spring dampening
            columnHeights[i] += (targetHeights[i] - columnHeights[i]) * 0.35f
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

        val paddingH = width * 0.03f
        val usableWidth = width - (paddingH * 2)
        val colSpacing = usableWidth / numColumns
        val dotRadius = (colSpacing * 0.26f).coerceIn(1.8f, 4.2f)
        val dotGap = dotRadius * 2.4f
        val centerY = height / 2f

        for (col in 0 until numColumns) {
            val colX = paddingH + (col * colSpacing) + (colSpacing / 2f)
            val heightRatio = columnHeights[col].coerceIn(0.05f, 1f)
            val activeDots = (heightRatio * maxDotsPerCol).toInt().coerceAtLeast(1)

            for (row in 0 until activeDots) {
                val yOffset = (row * dotGap)
                val intensity = row.toFloat() / maxDotsPerCol
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
                        // Perplexity Amber/Orange Glow (#FB923C / #F97316)
                        val r = 251
                        val g = (140 + (45 * intensity)).toInt().coerceIn(0, 255)
                        val b = (55 + (60 * intensity)).toInt().coerceIn(0, 255)
                        Color.rgb(r, g, b)
                    }
                }

                dotPaint.color = dotColor
                // Dimmer opacity for baseline dots, brighter for active voice
                dotPaint.alpha = if (activeDots <= 1 && micLevel <= 0.06f) 130 else (170 + (85 * intensity)).toInt().coerceIn(0, 255)

                // Top half dots
                val dotYTop = centerY - yOffset
                canvas.drawCircle(colX, dotYTop, dotRadius, dotPaint)

                // Bottom half mirrored dots
                if (row > 0) {
                    val dotYBottom = centerY + yOffset
                    canvas.drawCircle(colX, dotYBottom, dotRadius, dotPaint)
                }

                // Peak bright highlight on top dot
                if (row == activeDots - 1 && intensity > 0.4f) {
                    glowPaint.color = Color.WHITE
                    glowPaint.alpha = 150
                    canvas.drawCircle(colX, dotYTop, dotRadius * 0.55f, glowPaint)
                    if (row > 0) {
                        canvas.drawCircle(colX, centerY + yOffset, dotRadius * 0.55f, glowPaint)
                    }
                }
            }
        }
    }
}
