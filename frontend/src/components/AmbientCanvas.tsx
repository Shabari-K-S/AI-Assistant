import { useEffect, useRef } from 'react'

/**
 * Ambient "holo-mote" field: a lightweight canvas of drifting cyan motes.
 * Heavily optimized for mobile devices with frame throttling, visibility pause,
 * and dynamic particle scaling for ultra-low battery & CPU usage.
 */
export function AmbientCanvas() {
  const ref = useRef<HTMLCanvasElement>(null)
  const isMobile = typeof window !== 'undefined' && (window.innerWidth < 768 || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0))

  useEffect(() => {
    if (isMobile) return // 0% CPU and 0% GPU on mobile devices

    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    // Mobile: 12 motes, desktop: 45 motes
    const COUNT = isMobile ? 12 : 45
    const LINK_DIST = isMobile ? 70 : 110
    const dpr = Math.min(window.devicePixelRatio || 1, isMobile ? 1.0 : 1.5)
    const targetFps = isMobile ? 24 : 45
    const frameInterval = 1000 / targetFps

    let raf = 0
    let w = 0
    let h = 0
    let running = !document.hidden
    let lastDraw = 0

    interface Mote {
      x: number
      y: number
      vx: number
      vy: number
      r: number
      phase: number
    }
    let motes: Mote[] = []

    const resize = () => {
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      motes = Array.from({ length: COUNT }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.18,
        vy: (Math.random() - 0.5) * 0.18,
        r: Math.random() * (isMobile ? 1.0 : 1.4) + 0.4,
        phase: Math.random() * Math.PI * 2,
      }))
    }

    const step = (t: number) => {
      if (!running) return

      // Throttle framerate on mobile to conserve phone battery
      const elapsed = t - lastDraw
      if (elapsed < frameInterval) {
        raf = requestAnimationFrame(step)
        return
      }
      lastDraw = t - (elapsed % frameInterval)

      ctx.clearRect(0, 0, w, h)
      const time = t / 1000

      for (const m of motes) {
        m.x += m.vx
        m.y += m.vy
        if (m.x < -10) m.x = w + 10
        if (m.x > w + 10) m.x = -10
        if (m.y < -10) m.y = h + 10
        if (m.y > h + 10) m.y = -10
      }

      // Proximity links (skip on mobile for maximum GPU/CPU efficiency)
      if (!isMobile && !reduce) {
        ctx.lineWidth = 0.5
        for (let i = 0; i < motes.length; i++) {
          for (let j = i + 1; j < motes.length; j++) {
            const a = motes[i]
            const b = motes[j]
            const dx = a.x - b.x
            const dy = a.y - b.y
            const d2 = dx * dx + dy * dy
            if (d2 < LINK_DIST * LINK_DIST) {
              const alpha = (1 - Math.sqrt(d2) / LINK_DIST) * 0.14
              ctx.strokeStyle = `rgba(65, 230, 255, ${alpha})`
              ctx.beginPath()
              ctx.moveTo(a.x, a.y)
              ctx.lineTo(b.x, b.y)
              ctx.stroke()
            }
          }
        }
      }

      // Draw motes
      for (const m of motes) {
        const twinkle = 0.35 + 0.35 * (0.5 + 0.5 * Math.sin(time * 1.2 + m.phase))
        ctx.fillStyle = `rgba(65, 230, 255, ${twinkle})`
        ctx.beginPath()
        ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2)
        ctx.fill()
      }

      raf = requestAnimationFrame(step)
    }

    const onVisibility = () => {
      running = !document.hidden
      cancelAnimationFrame(raf)
      if (running) {
        lastDraw = performance.now()
        raf = requestAnimationFrame(step)
      }
    }

    resize()
    window.addEventListener('resize', resize, { passive: true })
    document.addEventListener('visibilitychange', onVisibility)
    raf = requestAnimationFrame(step)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 size-full opacity-60"
      style={{ willChange: 'transform', transform: 'translateZ(0)' }}
    />
  )
}
