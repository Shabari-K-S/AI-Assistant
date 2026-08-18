import { memo } from 'react'
import type { Snapshot } from '../types'
import { Wrench, Zap } from 'lucide-react'

interface Props {
  snap: Snapshot
  connected: boolean
}

export const TelemetryGauges = memo(function TelemetryGauges({ snap, connected }: Props) {
  const wakePercent = Math.min(100, Math.round(snap.wake_score * 100))
  const isHot = snap.wake_score >= snap.threshold
  const hasActiveTool = !!snap.active_tool

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full">
      {/* Gauge 1: Wake Score */}
      <div className="hud-panel p-2.5 rounded flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="hud-label text-[9px]">Wake Hit</span>
          <span
            className={`size-1.5 rounded-full ${
              isHot ? 'bg-[#ffc24b] shadow-[0_0_8px_#ffc24b]' : 'bg-[#41e6ff]'
            }`}
          />
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="font-mono text-lg font-bold text-[#e8fbff]">
            {snap.wake_score.toFixed(2)}
          </span>
          <span className="font-mono text-[10px] text-[#ffc24b]">
            THR {snap.threshold.toFixed(2)}
          </span>
        </div>
        <div className="w-full bg-[rgba(65,230,255,0.1)] h-1 rounded mt-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-150 ${
              isHot ? 'bg-[#ffc24b]' : 'bg-[#41e6ff]'
            }`}
            style={{ width: `${wakePercent}%` }}
          />
        </div>
      </div>

      {/* Gauge 2: Ambient / Active Tool */}
      <div className="hud-panel p-2.5 rounded flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="hud-label text-[9px]">
            {hasActiveTool ? 'Tool Running' : 'Ambient RMS'}
          </span>
          <span className={`font-mono text-[9px] ${hasActiveTool ? 'text-[#c084fc] font-bold animate-pulse' : 'text-[#7da4b8]'}`}>
            {hasActiveTool ? 'ACTIVE' : 'LIVE'}
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          {hasActiveTool ? (
            <span className="font-mono text-xs font-bold text-[#e879f9] truncate flex items-center gap-1" title={snap.active_tool?.name}>
              <Wrench size={11} className="shrink-0" />
              {snap.active_tool?.name}
            </span>
          ) : (
            <span className="font-mono text-lg font-bold text-[#e8fbff]">
              {snap.noise_floor.toFixed(3)}
            </span>
          )}
          <span className="font-mono text-[10px] text-[#7da4b8]">
            {hasActiveTool ? 'MCP' : 'RMS'}
          </span>
        </div>
        <div className="w-full bg-[rgba(65,230,255,0.1)] h-1 rounded mt-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${hasActiveTool ? 'bg-[#c084fc]' : 'bg-[#7ef3ff]'}`}
            style={{ width: hasActiveTool ? '100%' : `${Math.min(100, Math.round(snap.noise_floor * 1000))}%` }}
          />
        </div>
      </div>

      {/* Gauge 3: System Engine & TTFT */}
      <div className="hud-panel p-2.5 rounded flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="hud-label text-[9px]">Brain Engine</span>
          {snap.last_inference?.ttft_ms ? (
            <span className="font-mono text-[9px] text-[#fbbf24] font-semibold flex items-center gap-0.5">
              <Zap size={9} />
              {snap.last_inference.ttft_ms}ms
            </span>
          ) : (
            <span className="font-mono text-[9px] text-[#41e6ff]">STAGE 3</span>
          )}
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="font-mono text-sm font-semibold text-[#7ef3ff] truncate max-w-[120px]" title={snap.llm_model}>
            {snap.llm_model || 'OFFLINE'}
          </span>
          <span className="font-mono text-[10px] text-[#3e5c6d]">LLM</span>
        </div>
        <div className="w-full bg-[rgba(65,230,255,0.1)] h-1 rounded mt-1.5 overflow-hidden">
          <div
            className={`h-full ${connected ? 'bg-[#41e6ff]' : 'bg-[#ff5d5d]'}`}
            style={{ width: connected ? '100%' : '0%' }}
          />
        </div>
      </div>

      {/* Gauge 4: Speech Engine */}
      <div className="hud-panel p-2.5 rounded flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="hud-label text-[9px]">Voice Synthesis</span>
          <span
            className={`font-mono text-[9px] ${
              snap.muted ? 'text-[#ffc24b]' : 'text-[#41e6ff]'
            }`}
          >
            {snap.muted ? 'MUTED' : 'ACTIVE'}
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="font-mono text-sm font-semibold text-[#e8fbff]">
            {snap.tts ? snap.tts.toUpperCase() : 'LOCAL'}
          </span>
          <span className="font-mono text-[10px] text-[#7da4b8]">TTS</span>
        </div>
        <div className="w-full bg-[rgba(65,230,255,0.1)] h-1 rounded mt-1.5 overflow-hidden">
          <div
            className={`h-full ${snap.muted ? 'bg-[#ffc24b]' : 'bg-[#41e6ff]'}`}
            style={{ width: snap.muted ? '35%' : '100%' }}
          />
        </div>
      </div>
    </div>
  )
})
