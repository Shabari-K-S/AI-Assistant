import { memo, useMemo } from 'react'
import type { Phase } from '../types'
import { soundFx } from '../lib/soundFx'
import { Mic, Cpu, Activity, Volume2 } from 'lucide-react'

interface Props {
  size?: number
  phase?: Phase
  online?: boolean
  onClick?: () => void
}

interface OrbSpec {
  rgba: string
  hex: string
  pulseMin: number
  pulseMax: number
  pulseDur: number
  spin1Dur: number
  spin2Dur: number
  spin3Dur: number
  glowBlur: number
  label: string
}

const SPECS: Record<string, OrbSpec> = {
  standby: {
    rgba: '65, 230, 255',
    hex: '#41e6ff',
    pulseMin: 0.95,
    pulseMax: 1.05,
    pulseDur: 3.2,
    spin1Dur: 28,
    spin2Dur: 18,
    spin3Dur: 12,
    glowBlur: 28,
    label: 'STANDBY // READY',
  },
  listening: {
    rgba: '0, 255, 255',
    hex: '#00ffff',
    pulseMin: 0.88,
    pulseMax: 1.2,
    pulseDur: 0.75,
    spin1Dur: 8,
    spin2Dur: 5,
    spin3Dur: 3.5,
    glowBlur: 55,
    label: 'LISTENING // AUDIO UPLINK',
  },
  processing: {
    rgba: '186, 104, 255',
    hex: '#ba68ff',
    pulseMin: 0.9,
    pulseMax: 1.15,
    pulseDur: 0.6,
    spin1Dur: 4,
    spin2Dur: 2.8,
    spin3Dur: 1.8,
    glowBlur: 60,
    label: 'NEURAL INFERENCE // THINKING',
  },
  speaking: {
    rgba: '255, 194, 75',
    hex: '#ffc24b',
    pulseMin: 0.88,
    pulseMax: 1.18,
    pulseDur: 0.85,
    spin1Dur: 14,
    spin2Dur: 9,
    spin3Dur: 6,
    glowBlur: 48,
    label: 'VOCAL RESONANCE // SYNTHESIS',
  },
  offline: {
    rgba: '255, 93, 93',
    hex: '#ff5d5d',
    pulseMin: 0.98,
    pulseMax: 1.02,
    pulseDur: 4.0,
    spin1Dur: 45,
    spin2Dur: 35,
    spin3Dur: 25,
    glowBlur: 14,
    label: 'OFFLINE // STANDALONE',
  },
}

/**
 * J.A.R.V.I.S.-style Holographic Arc Reactor & Quantum Plasma Core.
 * Features multi-layered 3D-feeling gyroscopic spinning rings, holographic HUD ticks,
 * audio-reactive quantum ripple waves, and interactive tap-to-talk.
 */
export const CoreOrb = memo(function CoreOrb({
  size = 210,
  phase = 'standby',
  online = true,
  onClick,
}: Props) {
  const spec = SPECS[online ? phase : 'offline']

  // 36 Degree Ticks for the outer HUD Reticle Ring
  const hudTicks = useMemo(() => {
    const ticks = []
    for (let i = 0; i < 36; i++) {
      const angle = i * 10
      const isMajor = angle % 90 === 0
      const isSemi = angle % 30 === 0
      ticks.push({ angle, isMajor, isSemi })
    }
    return ticks
  }, [])

  const handleClick = () => {
    soundFx.click()
    onClick?.()
  }

  return (
    <div className="relative flex items-center justify-center select-none py-2">
      {/* Outer Glow Halo Atmosphere */}
      <div
        className="orb-halo transition-all duration-700"
        style={{
          boxShadow: `0 0 ${spec.glowBlur * 2}px rgba(${spec.rgba}, 0.28)`,
          willChange: 'transform, opacity',
        }}
      />

      {/* Audio-Reactive Expanding Quantum Ripples (Active when Listening / Speaking / Processing) */}
      {(phase === 'listening' || phase === 'speaking' || phase === 'processing') && (
        <>
          <div
            className="quantum-wave"
            style={{
              borderColor: `rgba(${spec.rgba}, 0.65)`,
              boxShadow: `0 0 16px rgba(${spec.rgba}, 0.35)`,
            }}
          />
          <div
            className="quantum-wave quantum-wave-delay"
            style={{
              borderColor: `rgba(${spec.rgba}, 0.5)`,
              boxShadow: `0 0 14px rgba(${spec.rgba}, 0.25)`,
            }}
          />
        </>
      )}

      {/* Main Holographic Reactor Container */}
      <div
        onClick={handleClick}
        title={onClick ? 'Tap Core to Toggle Voice Uplink (Tap-to-Talk)' : undefined}
        className={`orb relative transition-transform duration-300 ${
          onClick ? 'cursor-pointer active:scale-95 group' : ''
        }`}
        style={
          {
            '--s': `${size}px`,
            '--orb-rgba': spec.rgba,
            '--pulse-min': spec.pulseMin,
            '--pulse-max': spec.pulseMax,
            '--pulse-dur': `${spec.pulseDur}s`,
          } as React.CSSProperties
        }
      >
        {/* Layer 1: Vector Holographic Telemetry Reticle (SVG for ultra-sharp rendering) */}
        <svg
          viewBox="0 0 300 300"
          className="absolute inset-[-24%] size-[148%] pointer-events-none"
          style={{ willChange: 'transform' }}
        >
          {/* Subtle Hexagonal Background Matrix */}
          <polygon
            points="150,15 268,83 268,217 150,285 32,217 32,83"
            fill="none"
            stroke={`rgba(${spec.rgba}, 0.12)`}
            strokeWidth="1"
            strokeDasharray="4 8"
            className="animate-[spin_70s_linear_infinite]"
            style={{ transformOrigin: '150px 150px' }}
          />

          {/* Precision Circular Grid Lines */}
          <circle
            cx="150"
            cy="150"
            r="140"
            fill="none"
            stroke={`rgba(${spec.rgba}, 0.18)`}
            strokeWidth="0.75"
            strokeDasharray="3 6"
          />
          <circle
            cx="150"
            cy="150"
            r="125"
            fill="none"
            stroke={`rgba(${spec.rgba}, 0.25)`}
            strokeWidth="1"
          />

          {/* 36 HUD Compass Degree Ticks */}
          {hudTicks.map(({ angle, isMajor, isSemi }) => (
            <line
              key={angle}
              x1="150"
              y1={isMajor ? '8' : isSemi ? '14' : '18'}
              x2="150"
              y2="25"
              stroke={`rgba(${spec.rgba}, ${isMajor ? '0.85' : isSemi ? '0.55' : '0.25'})`}
              strokeWidth={isMajor ? '2' : isSemi ? '1.2' : '0.8'}
              transform={`rotate(${angle} 150 150)`}
            />
          ))}

          {/* 4 Cardinal HUD Triangle Brackets */}
          <polygon
            points="150,2 144,12 156,12"
            fill={spec.hex}
            className="drop-shadow-[0_0_6px_currentColor]"
          />
          <polygon
            points="150,298 144,288 156,288"
            fill={spec.hex}
            className="drop-shadow-[0_0_6px_currentColor]"
          />
          <polygon
            points="2,150 12,144 12,156"
            fill={spec.hex}
            className="drop-shadow-[0_0_6px_currentColor]"
          />
          <polygon
            points="298,150 288,144 288,156"
            fill={spec.hex}
            className="drop-shadow-[0_0_6px_currentColor]"
          />

          {/* High-tech Segmented Arc Laser Brackets (Rotating Slow Clockwise) */}
          <g
            className="animate-[spin_30s_linear_infinite]"
            style={{ transformOrigin: '150px 150px' }}
          >
            <path
              d="M 150 35 A 115 115 0 0 1 231 69"
              fill="none"
              stroke={spec.hex}
              strokeWidth="2.5"
              strokeLinecap="round"
              filter="drop-shadow(0 0 6px currentColor)"
            />
            <path
              d="M 150 265 A 115 115 0 0 1 69 231"
              fill="none"
              stroke={spec.hex}
              strokeWidth="2.5"
              strokeLinecap="round"
              filter="drop-shadow(0 0 6px currentColor)"
            />
          </g>

          {/* Counter-Rotating Inner Segmented Energy Ring */}
          <g
            className="animate-[spin-reverse_18s_linear_infinite]"
            style={{ transformOrigin: '150px 150px' }}
          >
            <path
              d="M 245 150 A 95 95 0 0 1 150 245"
              fill="none"
              stroke={`rgba(${spec.rgba}, 0.7)`}
              strokeWidth="1.8"
              strokeDasharray="6 12"
            />
            <path
              d="M 55 150 A 95 95 0 0 1 150 55"
              fill="none"
              stroke={`rgba(${spec.rgba}, 0.7)`}
              strokeWidth="1.8"
              strokeDasharray="6 12"
            />
          </g>
        </svg>

        {/* Layer 2: Gyroscopic Outer Segmented Ring with Photon Orbiters */}
        <div
          className="orb-ring transition-colors duration-500"
          style={{
            animation: `spin ${spec.spin1Dur}s linear infinite`,
            willChange: 'transform',
          }}
        >
          <span className="orb-dot" />
          <span className="orb-dot" style={{ top: 'auto', bottom: '-3.5px', left: '50%' }} />
          <span className="orb-dot" style={{ top: '50%', left: '-3.5px', marginTop: '-3.5px' }} />
          <span className="orb-dot" style={{ top: '50%', left: 'auto', right: '-3.5px', marginTop: '-3.5px' }} />
        </div>

        {/* Layer 3: Counter-Rotating Intermediate Ring */}
        <div
          className="orb-ring orb-ring2 transition-colors duration-500"
          style={{
            animation: `spin-reverse ${spec.spin2Dur}s linear infinite`,
            willChange: 'transform',
          }}
        >
          <span
            className="absolute top-1/2 -left-1 size-1.5 rounded-full"
            style={{ background: spec.hex, boxShadow: `0 0 8px ${spec.hex}` }}
          />
          <span
            className="absolute top-1/2 -right-1 size-1.5 rounded-full"
            style={{ background: spec.hex, boxShadow: `0 0 8px ${spec.hex}` }}
          />
        </div>

        {/* Layer 4: High-Frequency Inner Gyro Ring */}
        <div
          className="orb-ring orb-ring3 transition-colors duration-500"
          style={{
            animation: `spin ${spec.spin3Dur}s linear infinite`,
            willChange: 'transform',
          }}
        >
          <span className="orb-dot" style={{ width: '5px', height: '5px' }} />
        </div>

        {/* Layer 5: Glowing Quantum Plasma Reactor Core */}
        <div
          className="orb-core transition-all duration-500"
          style={{
            animation: `core-pulse var(--pulse-dur) ease-in-out infinite alternate`,
            willChange: 'transform',
          }}
        >
          {/* Internal Specular Core Flare */}
          <div className="absolute inset-[25%] rounded-full bg-gradient-to-tr from-white/90 via-cyan-100/60 to-transparent blur-[1px]" />
          <div className="absolute inset-[35%] rounded-full bg-white shadow-[0_0_15px_#ffffff] animate-pulse" />
        </div>

        {/* Interactive Hover / Tap Cue Icon Overlay */}
        {onClick && (
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
            <div className="p-2 rounded-full bg-[#03070b]/80 border border-[#41e6ff] text-[#41e6ff] shadow-[0_0_12px_#41e6ff]">
              <Mic size={14} className="animate-pulse" />
            </div>
          </div>
        )}
      </div>

      {/* Floating Side Telemetry Data Gauges (J.A.R.V.I.S. HUD Aesthetic) */}
      <div className="hidden xs:flex absolute inset-x-[-15%] sm:inset-x-[-25%] justify-between pointer-events-none font-mono text-[8.5px] sm:text-[9px] text-[#7da4b8] select-none">
        {/* Left Telemetry Pod */}
        <div className="flex flex-col items-start gap-1 bg-[rgba(6,14,21,0.65)] backdrop-blur-sm px-2.5 py-1.5 rounded border border-[rgba(65,230,255,0.15)]">
          <div className="flex items-center gap-1.5 text-[#41e6ff] font-bold">
            <Cpu size={10} />
            <span>NEURAL MATRIX</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_4px_#38ef7d]" />
            <span className="text-[#e8fbff]">GEMMA-4 ACTIVE</span>
          </div>
          <div className="text-[7.5px] sm:text-[8px] text-[#3e5c6d]">
            QUANTUM SYNC // 99.8%
          </div>
        </div>

        {/* Right Telemetry Pod */}
        <div className="flex flex-col items-end gap-1 bg-[rgba(6,14,21,0.65)] backdrop-blur-sm px-2.5 py-1.5 rounded border border-[rgba(65,230,255,0.15)] text-right">
          <div className="flex items-center gap-1.5 text-[#ffc24b] font-bold">
            <span>DSP AUDIO</span>
            <Volume2 size={10} />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[#e8fbff]">16 kHz FILTER</span>
            <Activity size={9} className="text-[#41e6ff] animate-pulse" />
          </div>
          <div className="text-[7.5px] sm:text-[8px] text-[#3e5c6d]">
            VAD GATE // ONLINE
          </div>
        </div>
      </div>
    </div>
  )
})
