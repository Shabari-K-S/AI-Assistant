import { memo, useEffect, useRef } from 'react'
import type { Phase } from '../types'

interface Props {
  phase: Phase
  online: boolean
  wakeScore: number
  noiseFloor: number
}

const PHASE_COLORS: Record<Phase, { primary: string; secondary: string; speed: number; amplitude: number }> = {
  standby: { primary: 'rgba(65, 230, 255, 0.75)', secondary: 'rgba(65, 230, 255, 0.15)', speed: 0.02, amplitude: 8 },
  listening: { primary: 'rgba(78, 205, 255, 0.95)', secondary: 'rgba(65, 230, 255, 0.35)', speed: 0.07, amplitude: 22 },
  processing: { primary: 'rgba(186, 104, 255, 0.9)', secondary: 'rgba(186, 104, 255, 0.3)', speed: 0.05, amplitude: 16 },
  speaking: { primary: 'rgba(255, 194, 75, 0.95)', secondary: 'rgba(255, 194, 75, 0.35)', speed: 0.09, amplitude: 26 },
}

/** Animated holographic audio wave oscilloscope + spectral bars */
export const AudioWaveform = memo(function AudioWaveform({
  phase,
  online,
  wakeScore,
  noiseFloor,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let offset = 0

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)

    const render = () => {
      const rect = canvas.getBoundingClientRect()
      const w = rect.width
      const h = rect.height
      const midY = h / 2

      ctx.clearRect(0, 0, w, h)

      const cfg = online
        ? PHASE_COLORS[phase]
        : { primary: 'rgba(80, 92, 100, 0.4)', secondary: 'rgba(80, 92, 100, 0.1)', speed: 0.005, amplitude: 3 }

      offset += cfg.speed

      // 1. Draw background spectrum bars
      const numBars = 32
      const barWidth = w / numBars - 2
      for (let i = 0; i < numBars; i++) {
        const x = i * (barWidth + 2) + 1
        const distFromCenter = Math.abs(i - numBars / 2) / (numBars / 2)
        const energy = Math.sin(offset * 2 + i * 0.4) * 0.5 + 0.5
        const boost = online && phase !== 'standby' ? (wakeScore * 20 + 8) : 4
        const barHeight = Math.max(3, (1 - distFromCenter * 0.6) * energy * (cfg.amplitude + boost))

        ctx.fillStyle = cfg.secondary
        ctx.fillRect(x, midY - barHeight / 2, barWidth, barHeight)
      }

      // 2. Draw dual flowing holographic sine waves
      ctx.lineWidth = 1.5
      ctx.strokeStyle = cfg.primary
      ctx.beginPath()

      for (let x = 0; x <= w; x += 3) {
        const norm = (x / w) * Math.PI * 4
        const env = Math.sin((x / w) * Math.PI) // smooth fade at edges
        const wave1 = Math.sin(norm + offset * 3) * (cfg.amplitude * 0.8)
        const wave2 = Math.sin(norm * 1.8 - offset * 2) * (cfg.amplitude * 0.4)
        const y = midY + (wave1 + wave2 + noiseFloor * 100) * env

        if (x === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      // 3. Secondary wave with phase inversion
      ctx.strokeStyle = cfg.secondary
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let x = 0; x <= w; x += 4) {
        const norm = (x / w) * Math.PI * 3
        const env = Math.sin((x / w) * Math.PI)
        const wave = Math.cos(norm - offset * 2.5) * (cfg.amplitude * 0.6)
        const y = midY + wave * env
        if (x === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      animId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [phase, online, wakeScore, noiseFloor])

  return (
    <div className="relative w-full h-12 overflow-hidden rounded border border-[rgba(65,230,255,0.15)] bg-[rgba(6,14,21,0.6)]">
      <canvas ref={canvasRef} className="size-full" />
      <div className="absolute top-1 left-2 font-mono text-[9px] tracking-widest text-[#7da4b8] flex items-center gap-2 pointer-events-none">
        <span className="inline-block size-1 rounded-full bg-[#41e6ff] animate-pulse" />
        OSCILLOSCOPE // {phase.toUpperCase()}
      </div>
    </div>
  )
})
