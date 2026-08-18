import { memo } from 'react'
import type { Phase } from '../types'

interface Props {
  size?: number
  phase?: Phase
  online?: boolean
}

interface OrbSpec {
  rgba: string
  colorName: string
  ring1Dur: number // seconds
  ring2Dur: number
  ring3Dur: number
  pulseMin: number
  pulseMax: number
  pulseDur: number
  glowBlur: number
}

const SPECS: Record<string, OrbSpec> = {
  standby: {
    rgba: '65, 230, 255',
    colorName: '#41e6ff',
    ring1Dur: 12,
    ring2Dur: 9,
    ring3Dur: 6,
    pulseMin: 0.94,
    pulseMax: 1.06,
    pulseDur: 2.8,
    glowBlur: 24,
  },
  listening: {
    rgba: '78, 205, 255',
    colorName: '#4ec7ff',
    ring1Dur: 4.5,
    ring2Dur: 3.2,
    ring3Dur: 2.2,
    pulseMin: 0.88,
    pulseMax: 1.15,
    pulseDur: 0.8,
    glowBlur: 42,
  },
  processing: {
    rgba: '186, 104, 255',
    colorName: '#ba68ff',
    ring1Dur: 2.0,
    ring2Dur: 1.4,
    ring3Dur: 0.95,
    pulseMin: 0.9,
    pulseMax: 1.12,
    pulseDur: 0.6,
    glowBlur: 48,
  },
  speaking: {
    rgba: '255, 194, 75',
    colorName: '#ffc24b',
    ring1Dur: 3.8,
    ring2Dur: 2.8,
    ring3Dur: 1.8,
    pulseMin: 0.88,
    pulseMax: 1.18,
    pulseDur: 0.75,
    glowBlur: 45,
  },
  offline: {
    rgba: '75, 88, 98',
    colorName: '#4b5862',
    ring1Dur: 18,
    ring2Dur: 14,
    ring3Dur: 9,
    pulseMin: 0.96,
    pulseMax: 1.03,
    pulseDur: 4.0,
    glowBlur: 10,
  },
}

/** 
 * Arc-reactor core powered by GPU-accelerated CSS compositing.
 * Zero CPU animation loops for maximum mobile battery efficiency.
 */
export const CoreOrb = memo(function CoreOrb({ size = 200, phase = 'standby', online = true }: Props) {
  const spec = SPECS[online ? phase : 'offline']

  return (
    <div
      className="orb select-none"
      style={
        {
          '--s': `${size}px`,
          '--orb-rgba': spec.rgba,
          '--ring1-dur': `${spec.ring1Dur}s`,
          '--ring2-dur': `${spec.ring2Dur}s`,
          '--ring3-dur': `${spec.ring3Dur}s`,
          '--pulse-min': spec.pulseMin,
          '--pulse-max': spec.pulseMax,
          '--pulse-dur': `${spec.pulseDur}s`,
        } as React.CSSProperties
      }
    >
      {/* Outer energy aura */}
      <div
        className="orb-halo transition-all duration-700"
        style={{
          boxShadow: `0 0 ${spec.glowBlur * 1.5}px rgba(${spec.rgba}, 0.25)`,
          willChange: 'transform, opacity',
        }}
      />

      {/* Hexagon / Cyber boundary overlay */}
      <div className="absolute inset-[-18%] pointer-events-none opacity-30 flex items-center justify-center">
        <svg viewBox="0 0 100 100" className="size-full animate-[spin_60s_linear_infinite]" style={{ willChange: 'transform' }}>
          <polygon
            points="50,2 93,25 93,75 50,98 7,75 7,25"
            fill="none"
            stroke={`rgb(${spec.rgba})`}
            strokeWidth="0.5"
            strokeDasharray="4 8"
          />
        </svg>
      </div>

      {/* Outer ring with energy node (GPU-composited CSS animation) */}
      <div
        className="orb-ring orb-ring1 transition-colors duration-500"
        style={{
          animation: `spin var(--ring1-dur) linear infinite`,
          willChange: 'transform',
        }}
      >
        <span className="orb-dot" />
        <span
          className="orb-dot"
          style={{ top: 'auto', bottom: '-3px', left: '50%' }}
        />
      </div>

      {/* Segmented middle ring (GPU-composited CSS counter-rotation) */}
      <div
        className="orb-ring orb-ring2 transition-colors duration-500"
        style={{
          animation: `spin-reverse var(--ring2-dur) linear infinite`,
          willChange: 'transform',
        }}
      >
        <span
          className="absolute top-1/2 -left-1 size-1 rounded-full"
          style={{ background: `rgb(${spec.rgba})`, boxShadow: `0 0 8px rgb(${spec.rgba})` }}
        />
        <span
          className="absolute top-1/2 -right-1 size-1 rounded-full"
          style={{ background: `rgb(${spec.rgba})`, boxShadow: `0 0 8px rgb(${spec.rgba})` }}
        />
      </div>

      {/* Inner gyro ring */}
      <div
        className="orb-ring orb-ring3 transition-colors duration-500"
        style={{
          animation: `spin var(--ring3-dur) linear infinite`,
          willChange: 'transform',
        }}
      >
        <span className="orb-dot" />
      </div>

      {/* Core Plasma Reactor */}
      <div
        className="orb-core transition-all duration-500"
        style={{
          animation: `core-pulse var(--pulse-dur) ease-in-out infinite alternate`,
          willChange: 'transform',
        }}
      />
    </div>
  )
})

