import { memo, useEffect, useState } from 'react'
import type { Snapshot } from '../types'
import { soundFx } from '../lib/soundFx'
import { Sliders, Volume2, VolumeX, Shield, Cpu, Mic, Radio, Clock, AudioLines } from 'lucide-react'

interface Props {
  snap: Snapshot
  connected: boolean
  onThreshold: (value: number) => void
  onMuted: (muted: boolean) => void
}

/** Left HUD panel: live sensor controls + system telemetry readouts. */
export const SensorPanel = memo(function SensorPanel({
  snap,
  connected,
  onThreshold,
  onMuted,
}: Props) {
  const [localThr, setLocalThr] = useState(snap.threshold)

  useEffect(() => {
    setLocalThr(snap.threshold)
  }, [snap.threshold])

  const commitThreshold = () => {
    soundFx.click()
    onThreshold(Number(localThr.toFixed(3)))
  }

  const handleMuteToggle = () => {
    soundFx.click()
    onMuted(!snap.muted)
  }

  const uptime =
    snap.since > 0
      ? Math.floor(Date.now() / 1000 - snap.since) + 's'
      : '—'

  const Row = ({
    k,
    v,
    accent,
    icon: Icon,
  }: {
    k: string
    v: string
    accent?: boolean
    icon?: typeof Sliders
  }) => (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-[rgba(65,230,255,0.05)]">
      <span className="hud-label text-[9.5px] flex items-center gap-1.5">
        {Icon && <Icon size={10} className="text-[#41e6ff]" />}
        <span>{k}</span>
      </span>
      <span
        className={`font-mono text-xs tracking-wider truncate max-w-[120px] ${
          accent ? 'text-[#41e6ff] font-semibold' : 'text-[#7da4b8]'
        }`}
        title={v}
      >
        {v}
      </span>
    </div>
  )

  return (
    <aside className="hud-panel flex w-full md:w-64 lg:w-72 shrink-0 flex-col overflow-y-auto border-r border-r-[rgba(65,230,255,0.14)] bg-[rgba(4,9,15,0.6)]">
      {/* 1. Sensory Control Bay */}
      <div className="border-b border-[rgba(65,230,255,0.1)] p-4">
        <div className="hud-label mb-3 text-[10px] flex items-center gap-1.5 text-[#41e6ff]">
          <Sliders size={12} />
          <span>Sensor Calibration</span>
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="hud-label text-[9px]">Wake Sensitivity</span>
            <span className="hud-num text-xs font-bold">{localThr.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.1}
            max={1}
            step={0.01}
            value={localThr}
            onChange={(e) => setLocalThr(Number(e.target.value))}
            onPointerUp={commitThreshold}
            onKeyUp={commitThreshold}
            className="w-full cursor-pointer h-1.5 bg-[rgba(65,230,255,0.15)] rounded-lg appearance-none accent-[#41e6ff]"
            aria-label="Wake word threshold"
          />
          <div className="flex justify-between text-[8px] font-mono text-[#3e5c6d] mt-1">
            <span>MORE SENSITIVE (0.1)</span>
            <span>STRICT (1.0)</span>
          </div>
        </div>

        <button
          onClick={handleMuteToggle}
          disabled={!connected}
          className={`flex w-full items-center justify-center gap-2 border py-2.5 rounded font-display text-[10.5px] tracking-[0.2em] transition-all disabled:opacity-40 active:scale-95 ${
            snap.muted
              ? 'border-[rgba(255,194,75,0.6)] bg-[rgba(255,194,75,0.1)] text-[#ffc24b] shadow-[0_0_12px_rgba(255,194,75,0.2)]'
              : 'border-[rgba(65,230,255,0.3)] bg-[rgba(65,230,255,0.06)] text-[#7ef3ff] hover:bg-[rgba(65,230,255,0.14)]'
          }`}
        >
          {snap.muted ? <VolumeX size={13} className="text-[#ffc24b]" /> : <Volume2 size={13} className="text-[#41e6ff]" />}
          <span>VOICE OUTPUT: {snap.muted ? 'MUTED' : 'ACTIVE'}</span>
        </button>
      </div>

      {/* 2. System Telemetry Array */}
      <div className="flex-1 p-4">
        <div className="hud-label mb-2.5 text-[10px] flex items-center gap-1.5 text-[#41e6ff]">
          <Shield size={12} />
          <span>System Matrix</span>
        </div>
        <Row k="Phase" v={snap.phase.toUpperCase()} accent />
        <Row k="Wake Word" v={snap.wake_word.toUpperCase()} icon={Mic} />
        <Row k="Brain LLM" v={snap.llm_model || '—'} icon={Cpu} />
        <Row k="Speech STT" v={snap.stt_model.toUpperCase()} icon={AudioLines} />
        <Row k="Audio TTS" v={snap.tts.toUpperCase()} icon={Radio} />
        <Row k="Noise Level" v={snap.noise_floor.toFixed(4)} />
        <Row k="Uptime" v={uptime} icon={Clock} />
      </div>

      {/* 3. Link Status */}
      <div className="border-t border-[rgba(65,230,255,0.1)] p-3.5 bg-[rgba(3,7,12,0.4)]">
        <div className="flex items-center justify-between">
          <span className="hud-label text-[9px]">Telemetry Uplink</span>
          <span className="flex items-center gap-1.5 font-mono text-[9px] tracking-widest">
            <span
              className={`inline-block size-1.5 rounded-full ${
                connected ? 'bg-[#41e6ff]' : 'bg-[#ff5d5d]'
              }`}
              style={{ boxShadow: `0 0 6px ${connected ? '#41e6ff' : '#ff5d5d'}` }}
            />
            <span className={connected ? 'text-[#41e6ff]' : 'text-[#ff5d5d]'}>
              {connected ? 'ONLINE :2027' : 'OFFLINE'}
            </span>
          </span>
        </div>
        <p className="mt-1 font-mono text-[8.5px] leading-relaxed tracking-wider text-[#3e5c6d]">
          {connected
            ? 'DIRECT SSE PROTOCOL STREAM // 250ms CADENCE'
            : 'HOST DISCONNECTED — START BACKEND ENGINE'}
        </p>
      </div>
    </aside>
  )
})
