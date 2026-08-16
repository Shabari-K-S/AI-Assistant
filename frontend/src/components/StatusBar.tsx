import { useEffect, useRef, useState } from 'react'
import { animate, stagger } from 'animejs'
import type { Phase } from '../types'
import { soundFx } from '../lib/soundFx'
import { Volume2, VolumeX, Maximize2, Minimize2, Radio, Sparkles } from 'lucide-react'

interface Props {
  phase: Phase
  online: boolean
  wakeWord: string
}

function useClock(): string {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(t)
  }, [])
  return now.toLocaleTimeString(undefined, { hour12: false })
}

const PHASE_LABEL: Record<Phase, string> = {
  standby: 'STAND BY',
  listening: 'LISTENING',
  processing: 'REASONING',
  speaking: 'REPLYING',
}

/** Top HUD bar: identity, phase, live state lights, audio controls. */
export function StatusBar({ phase, online, wakeWord }: Props) {
  const clock = useClock()
  const barRef = useRef<HTMLDivElement>(null)
  const [soundEnabled, setSoundEnabled] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const bar = barRef.current
    if (!bar) return
    const t = animate(bar.querySelectorAll('.status-light'), {
      opacity: [0.2, 1],
      duration: 600,
      ease: 'outQuad',
      delay: stagger(160),
    })
    const f = animate(bar, { opacity: [0, 1], duration: 500, ease: 'outQuad' })
    return () => {
      t.cancel()
      f.cancel()
    }
  }, [])

  const toggleSound = () => {
    const next = !soundEnabled
    setSoundEnabled(next)
    soundFx.setEnabled(next)
    if (next) soundFx.click()
  }

  const toggleFullscreen = () => {
    soundFx.click()
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {})
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {})
    }
  }

  const busy = phase !== 'standby'

  return (
    <header
      ref={barRef}
      className="relative flex h-12 sm:h-14 shrink-0 items-center justify-between border-b border-[rgba(65,230,255,0.18)] bg-[rgba(5,11,18,0.88)] backdrop-blur-md px-3 sm:px-6 opacity-0 z-40"
    >
      {/* Identity */}
      <div className="flex items-center gap-2 sm:gap-3">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Radio size={15} className={`text-[#41e6ff] ${online ? 'animate-pulse' : 'opacity-40'}`} />
          <div className="font-display text-sm sm:text-base font-bold tracking-[0.25em] sm:tracking-[0.32em] text-[#e8fbff] flex items-center">
            S<span className="text-[#41e6ff]">.</span>A
            <span className="text-[#41e6ff]">.</span>R
            <span className="text-[#41e6ff]">.</span>A
          </div>
        </div>
        <span className="hidden font-mono text-[9px] tracking-[0.2em] text-[#3e5c6d] xl:inline border-l border-[rgba(65,230,255,0.15)] pl-3">
          HOLOGRAPHIC REASONING INTERFACE // MK-IV
        </span>
      </div>

      {/* Center status gauges */}
      <div className="flex items-center gap-2 sm:gap-6">
        <span className="hidden xs:flex items-center gap-1.5">
          <span className={`status-light ${online ? 'status-light-on' : 'bg-[#3e5c6d]'}`} />
          <span className="hud-label text-[9px] sm:text-[9.5px]">Core</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className={`status-light ${
              online && busy
                ? phase === 'speaking'
                  ? 'bg-[#ffc24b] shadow-[0_0_8px_#ffc24b]'
                  : phase === 'processing'
                    ? 'bg-[#ba68ff] shadow-[0_0_8px_#ba68ff]'
                    : 'status-light-on'
                : 'bg-[#3e5c6d]'
            }`}
          />
          <span className="hud-label text-[9px] sm:text-[9.5px] font-semibold">{online ? PHASE_LABEL[phase] : 'Offline'}</span>
        </span>
        <span className="hidden md:flex items-center gap-1.5">
          <Sparkles size={11} className={online ? 'text-[#41e6ff]' : 'text-[#3e5c6d]'} />
          <span className="font-mono text-[10px] tracking-wider text-[#7da4b8]">
            WAKE: <strong className="text-[#41e6ff]">{wakeWord.toUpperCase()}</strong>
          </span>
        </span>
      </div>

      {/* Right telemetry & controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={toggleSound}
          title={soundEnabled ? 'Mute HUD Audio Effects' : 'Unmute HUD Audio Effects'}
          className="p-1 sm:p-1.5 text-[#7da4b8] hover:text-[#41e6ff] bg-[rgba(65,230,255,0.05)] hover:bg-[rgba(65,230,255,0.12)] border border-[rgba(65,230,255,0.15)] rounded transition-all"
        >
          {soundEnabled ? <Volume2 size={13} /> : <VolumeX size={13} className="text-[#ff5d5d]" />}
        </button>

        <button
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
          className="p-1.5 text-[#7da4b8] hover:text-[#41e6ff] bg-[rgba(65,230,255,0.05)] hover:bg-[rgba(65,230,255,0.12)] border border-[rgba(65,230,255,0.15)] rounded transition-all hidden sm:block"
        >
          {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        </button>

        <span className="hud-num text-[11px] sm:text-xs tracking-wider pl-0.5 sm:pl-1 font-bold hidden sm:inline">{clock}</span>

        <div className="flex items-center gap-1 sm:gap-1.5 border border-[rgba(65,230,255,0.18)] bg-[rgba(6,14,21,0.6)] px-1.5 sm:px-2 py-0.5 sm:py-1 rounded">
          <span
            className={`inline-block size-1.5 sm:size-2 rounded-full ${
              online ? 'bg-[#41e6ff]' : 'bg-[#ff5d5d]'
            }`}
            style={{ boxShadow: `0 0 8px ${online ? '#41e6ff' : '#ff5d5d'}` }}
          />
          <span className="font-mono text-[8px] sm:text-[9px] tracking-wider text-[#7da4b8]">
            {online ? 'LINKED' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  )
}
