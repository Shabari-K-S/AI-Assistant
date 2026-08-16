import { useEffect, useRef } from 'react'
import { animate, type JSAnimation } from 'animejs'
import type { Phase } from '../types'

interface Props {
  size?: number
  phase?: Phase
  online?: boolean
}

interface OrbSpec {
  rgba: string
  colorName: string
  rings: [number, number, number] // rotation durations ms
  pulse: [number, number] // core scale range
  pulseDur: number
  glowBlur: number
}

const SPECS: Record<string, OrbSpec> = {
  standby: {
    rgba: '65, 230, 255',
    colorName: '#41e6ff',
    rings: [12000, -9000, 6000],
    pulse: [0.94, 1.06],
    pulseDur: 2800,
    glowBlur: 24,
  },
  listening: {
    rgba: '78, 205, 255',
    colorName: '#4ec7ff',
    rings: [4500, -3200, 2200],
    pulse: [0.88, 1.15],
    pulseDur: 800,
    glowBlur: 42,
  },
  processing: {
    rgba: '186, 104, 255',
    colorName: '#ba68ff',
    rings: [2000, -1400, 950],
    pulse: [0.9, 1.12],
    pulseDur: 600,
    glowBlur: 48,
  },
  speaking: {
    rgba: '255, 194, 75',
    colorName: '#ffc24b',
    rings: [3800, -2800, 1800],
    pulse: [0.88, 1.18],
    pulseDur: 750,
    glowBlur: 45,
  },
  offline: {
    rgba: '75, 88, 98',
    colorName: '#4b5862',
    rings: [18000, -14000, 9000],
    pulse: [0.96, 1.03],
    pulseDur: 4000,
    glowBlur: 10,
  },
}

/** Arc-reactor core whose spin/pulse/tint follow the assistant's phase. */
export function CoreOrb({ size = 200, phase = 'standby', online = true }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const ring1Ref = useRef<HTMLDivElement>(null)
  const ring2Ref = useRef<HTMLDivElement>(null)
  const ring3Ref = useRef<HTMLDivElement>(null)
  const coreRef = useRef<HTMLDivElement>(null)
  const anims = useRef<JSAnimation[]>([])

  useEffect(() => {
    const spec = SPECS[online ? phase : 'offline']

    anims.current.forEach((a) => a.cancel())
    anims.current = []

    if (ring1Ref.current) {
      anims.current.push(
        animate(ring1Ref.current, {
          rotate: 360,
          duration: Math.abs(spec.rings[0]),
          ease: 'linear',
          loop: true,
        }),
      )
    }
    if (ring2Ref.current) {
      anims.current.push(
        animate(ring2Ref.current, {
          rotate: spec.rings[1] < 0 ? -360 : 360,
          duration: Math.abs(spec.rings[1]),
          ease: 'linear',
          loop: true,
        }),
      )
    }
    if (ring3Ref.current) {
      anims.current.push(
        animate(ring3Ref.current, {
          rotate: 360,
          duration: Math.abs(spec.rings[2]),
          ease: 'linear',
          loop: true,
        }),
      )
    }
    if (coreRef.current) {
      anims.current.push(
        animate(coreRef.current, {
          scale: spec.pulse,
          duration: spec.pulseDur,
          ease: 'easeInOutQuad',
          direction: 'alternate',
          loop: true,
        }),
      )
    }

    return () => {
      anims.current.forEach((a) => a.cancel())
      anims.current = []
    }
  }, [phase, online, size])

  const currentSpec = SPECS[online ? phase : 'offline']

  return (
    <div
      ref={rootRef}
      className="orb select-none"
      style={
        {
          '--s': `${size}px`,
          '--orb-rgba': currentSpec.rgba,
        } as React.CSSProperties
      }
    >
      {/* Outer energy aura */}
      <div
        className="orb-halo transition-all duration-700"
        style={{
          boxShadow: `0 0 ${currentSpec.glowBlur * 1.5}px rgba(${currentSpec.rgba}, 0.25)`,
        }}
      />

      {/* Hexagon / Cyber boundary overlay */}
      <div className="absolute inset-[-18%] pointer-events-none opacity-30 flex items-center justify-center">
        <svg viewBox="0 0 100 100" className="size-full animate-[spin_60s_linear_infinite]">
          <polygon
            points="50,2 93,25 93,75 50,98 7,75 7,25"
            fill="none"
            stroke={`rgb(${currentSpec.rgba})`}
            strokeWidth="0.5"
            strokeDasharray="4 8"
          />
        </svg>
      </div>

      {/* Outer ring with energy node */}
      <div ref={ring1Ref} className="orb-ring orb-ring1 transition-colors duration-500">
        <span className="orb-dot" />
        <span
          className="orb-dot"
          style={{ top: 'auto', bottom: '-3px', left: '50%' }}
        />
      </div>

      {/* Segmented middle ring */}
      <div ref={ring2Ref} className="orb-ring orb-ring2 transition-colors duration-500">
        <span
          className="absolute top-1/2 -left-1 size-1 rounded-full"
          style={{ background: `rgb(${currentSpec.rgba})`, boxShadow: `0 0 8px rgb(${currentSpec.rgba})` }}
        />
        <span
          className="absolute top-1/2 -right-1 size-1 rounded-full"
          style={{ background: `rgb(${currentSpec.rgba})`, boxShadow: `0 0 8px rgb(${currentSpec.rgba})` }}
        />
      </div>

      {/* Inner gyro ring */}
      <div ref={ring3Ref} className="orb-ring orb-ring3 transition-colors duration-500">
        <span className="orb-dot" />
      </div>

      {/* Core Plasma Reactor */}
      <div ref={coreRef} className="orb-core transition-all duration-500" />
    </div>
  )
}
