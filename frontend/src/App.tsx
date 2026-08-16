import { useState } from 'react'
import { AmbientCanvas } from './components/AmbientCanvas'
import { StatusBar } from './components/StatusBar'
import { SensorPanel } from './components/SensorPanel'
import { FeedPanel } from './components/FeedPanel'
import { CoreOrb } from './components/CoreOrb'
import { WakeMeter } from './components/WakeMeter'
import { AudioWaveform } from './components/AudioWaveform'
import { CommandDeck } from './components/CommandDeck'
import { TelemetryGauges } from './components/TelemetryGauges'
import { useAssistant } from './hooks/useAssistant'
import { soundFx } from './lib/soundFx'
import { Sliders, MessageSquare, Eye, EyeOff } from 'lucide-react'

const PHASE_TAG: Record<string, string> = {
  standby: 'AWAITING WAKE WORD OR COMMAND',
  listening: 'RECEIVING VOICE SIGNAL — SPEAK YOUR QUERY',
  processing: 'SYNTHESIZING REASONING & TOOLS',
  speaking: 'STREAMING AUDIO TRANSMISSION',
}

export default function App() {
  const { snap, logs, connected, setThreshold, setMuted, sendPrompt, clearLogs } = useAssistant()
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [scanlinesActive, setScanlinesActive] = useState(true)

  const phaseLabel =
    PHASE_TAG[snap.phase] ?? (connected ? 'SYSTEM ACTIVE' : 'HOST BACKEND OFFLINE')

  const toggleLeft = () => {
    soundFx.click()
    setShowLeftSidebar((prev) => !prev)
  }

  const toggleRight = () => {
    soundFx.click()
    setShowRightSidebar((prev) => !prev)
  }

  const toggleScanlines = () => {
    soundFx.click()
    setScanlinesActive((prev) => !prev)
  }

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-[#03070b] text-[#e8fbff] select-none">
      {/* Background ambient particle field & holo grid */}
      <AmbientCanvas />
      <div className="hud-grid pointer-events-none fixed inset-0 z-0" />
      {scanlinesActive && (
        <div className="scanlines pointer-events-none fixed inset-0 z-[60] opacity-75" />
      )}

      {/* Top telemetry bar */}
      <StatusBar phase={snap.phase} online={connected} wakeWord={snap.wake_word} />

      {/* Main command deck body */}
      <div className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        {/* Left Sensor Matrix */}
        {showLeftSidebar && (
          <SensorPanel
            snap={snap}
            connected={connected}
            onThreshold={setThreshold}
            onMuted={setMuted}
          />
        )}

        {/* Center Command Core */}
        <main className="flex min-w-0 flex-1 flex-col items-center justify-between p-3 sm:p-5 overflow-y-auto space-y-4">
          {/* Top banner controls */}
          <div className="w-full flex items-center justify-between max-w-4xl px-2">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleLeft}
                title="Toggle Sensor Panel"
                className={`p-1.5 rounded border text-[11px] font-mono flex items-center gap-1.5 transition-all ${
                  showLeftSidebar
                    ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                    : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                }`}
              >
                <Sliders size={12} />
                <span className="hidden sm:inline">SENSORS</span>
              </button>

              <button
                onClick={toggleScanlines}
                title="Toggle CRT Scanline Filter"
                className={`p-1.5 rounded border text-[11px] font-mono flex items-center gap-1.5 transition-all ${
                  scanlinesActive
                    ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                    : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                }`}
              >
                {scanlinesActive ? <Eye size={12} /> : <EyeOff size={12} />}
                <span className="hidden sm:inline">SCANLINES</span>
              </button>
            </div>

            <div className="font-mono text-[9px] tracking-[0.25em] text-[#41e6ff] bg-[rgba(65,230,255,0.06)] px-2.5 py-1 rounded border border-[rgba(65,230,255,0.18)]">
              [ SECTOR 01 // MAIN_CORE ]
            </div>

            <button
              onClick={toggleRight}
              title="Toggle Transmission Feed"
              className={`p-1.5 rounded border text-[11px] font-mono flex items-center gap-1.5 transition-all ${
                showRightSidebar
                  ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                  : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
              }`}
            >
              <MessageSquare size={12} />
              <span className="hidden sm:inline">LOGS</span>
            </button>
          </div>

          {/* Core Orb & Reactor Display */}
          <div className="flex flex-col items-center justify-center my-auto py-2">
            <CoreOrb size={200} phase={snap.phase} online={connected} />

            {/* Dynamic Phase Display */}
            <div className="text-center mt-3">
              <div
                className={`font-display text-2xl sm:text-3xl font-bold tracking-[0.35em] transition-colors duration-500 ${
                  !connected
                    ? 'text-[#ff5d5d]'
                    : snap.phase === 'speaking'
                      ? 'text-[#ffc24b] drop-shadow-[0_0_12px_rgba(255,194,75,0.6)]'
                      : snap.phase === 'processing'
                        ? 'text-[#ba68ff] drop-shadow-[0_0_12px_rgba(186,104,255,0.6)]'
                        : 'text-[#e8fbff] drop-shadow-[0_0_12px_rgba(65,230,255,0.5)]'
                }`}
              >
                {connected ? snap.phase.toUpperCase() : 'OFFLINE'}
                <span className="cursor-blink ml-1" aria-hidden />
              </div>
              <div className="mt-1 font-mono text-[10.5px] sm:text-xs tracking-[0.22em] text-[#7da4b8]">
                {connected ? phaseLabel : 'START ASSISTANT BACKEND: ./run.sh'}
              </div>
            </div>
          </div>

          {/* Lower Control Stack (Visualizer + Gauges + WakeMeter + Terminal Deck) */}
          <div className="w-full max-w-2xl space-y-3">
            {/* Audio Waveform Oscilloscope */}
            <AudioWaveform
              phase={snap.phase}
              online={connected}
              wakeScore={snap.wake_score}
              noiseFloor={snap.noise_floor}
            />

            {/* Wake Word Sensitivity Meter */}
            <WakeMeter
              score={snap.wake_score}
              threshold={snap.threshold}
              noiseFloor={snap.noise_floor}
            />

            {/* 4-Column Quick Telemetry Gauges */}
            <TelemetryGauges snap={snap} connected={connected} />

            {/* Interactive Terminal Uplink Input */}
            <CommandDeck onSend={sendPrompt} connected={connected} />
          </div>
        </main>

        {/* Right Transmission & Telemetry Feed */}
        {showRightSidebar && (
          <FeedPanel snap={snap} logs={logs} onClearLogs={clearLogs} />
        )}
      </div>
    </div>
  )
}
