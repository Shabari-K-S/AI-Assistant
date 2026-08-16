import { useEffect, useRef } from 'react'

/**
 * Ambient "holo-mote" field: a lightweight canvas of drifting cyan motes with
 * proximity links. Pauses when the tab is hidden; respects reduced-motion.
 */
export function AmbientCanvas() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    const LINK_DIST = 120
    const COUNT = 55

    let raf = 0
    let w = 0
    let h = 0
    let running = !document.hidden

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
        vx: (Math.random() - 0.5) * 0.16,
        vy: (Math.random() - 0.5) * 0.16,
        r: Math.random() * 1.4 + 0.5,
        phase: Math.random() * Math.PI * 2,
      }))
    }

    const step = (t: number) => {
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

      // proximity links
      ctx.lineWidth = 0.5
      for (let i = 0; i < motes.length; i++) {
        for (let j = i + 1; j < motes.length; j++) {
          const a = motes[i]
          const b = motes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const d2 = dx * dx + dy * dy
          if (d2 < LINK_DIST * LINK_DIST) {
            const alpha = (1 - Math.sqrt(d2) / LINK_DIST) * 0.16
            ctx.strokeStyle = `rgba(65, 230, 255, ${alpha})`
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
      }

      // motes
      for (const m of motes) {
        const twinkle = 0.35 + 0.4 * (0.5 + 0.5 * Math.sin(time * 1.4 + m.phase))
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
      if (running) raf = requestAnimationFrame(step)
    }

    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', onVisibility)
    resize()
    if (!reduce) raf = requestAnimationFrame(step)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
    />
  )
}
