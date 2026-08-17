import { useState, useEffect } from 'react'
import { AmbientCanvas } from './components/AmbientCanvas'
import { StatusBar } from './components/StatusBar'
import { SensorPanel } from './components/SensorPanel'
import { FeedPanel } from './components/FeedPanel'
import { CoreOrb } from './components/CoreOrb'
import { WakeMeter } from './components/WakeMeter'
import { AudioWaveform } from './components/AudioWaveform'
import { CommandDeck } from './components/CommandDeck'
import { TelemetryGauges } from './components/TelemetryGauges'
import { McpConfigPanel } from './components/McpConfigPanel'
import { useAssistant } from './hooks/useAssistant'
import { soundFx } from './lib/soundFx'
import { Sliders, MessageSquare, Eye, EyeOff, Radio, Cpu } from 'lucide-react'

const PHASE_TAG: Record<string, string> = {
  standby: 'AWAITING WAKE WORD OR COMMAND',
  listening: 'RECEIVING VOICE SIGNAL — SPEAK YOUR QUERY',
  processing: 'SYNTHESIZING REASONING & TOOLS',
  speaking: 'STREAMING AUDIO TRANSMISSION',
}

type MobileTab = 'mcp' | 'core' | 'logs'
type CenterView = 'core' | 'mcp'

export default function App() {
  const {
    snap,
    logs,
    connected,
    setThreshold,
    setMuted,
    sendPrompt,
    triggerPtt,
    clearLogs,
  } = useAssistant()
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [scanlinesActive, setScanlinesActive] = useState(true)
  const [webListening, setWebListening] = useState(false)
  const [centerView, setCenterView] = useState<CenterView>('core')
  const [mobileTab, setMobileTab] = useState<MobileTab>('core')
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768)

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (!mobile) {
        setMobileTab('core')
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const activePhase = webListening ? 'listening' : snap.phase
  const activeSnap = webListening ? { ...snap, phase: 'listening' as const, wake_score: 1.0 } : snap

  const phaseLabel =
    PHASE_TAG[activePhase] ?? (connected ? 'SYSTEM ACTIVE' : 'HOST BACKEND OFFLINE')

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

  const switchMobileTab = (tab: MobileTab) => {
    soundFx.click()
    setMobileTab(tab)
  }

  const handlePromptFromMcp = (text: string) => {
    sendPrompt(text)
    setCenterView('core')
    if (isMobile) setMobileTab('core')
  }

  return (
    <div className="relative flex h-[100dvh] w-screen flex-col overflow-hidden bg-[#03070b] text-[#e8fbff] select-none">
      {/* Background ambient particle field & holo grid */}
      <AmbientCanvas />
      <div className="hud-grid pointer-events-none fixed inset-0 z-0" />
      {scanlinesActive && (
        <div className="scanlines pointer-events-none fixed inset-0 z-[60] opacity-75" />
      )}

      {/* Top telemetry bar */}
      <StatusBar phase={activePhase} online={connected} wakeWord={snap.wake_word} />

      {/* Main command deck body */}
      <div className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        {/* Left Sensor Matrix (Desktop only) */}
        {!isMobile && showLeftSidebar && (
          <SensorPanel
            snap={activeSnap}
            connected={connected}
            onThreshold={setThreshold}
            onMuted={setMuted}
          />
        )}

        {/* Center View: Either Core HUD or MCP Configuration Panel */}
        {(!isMobile && centerView === 'mcp') || (isMobile && mobileTab === 'mcp') ? (
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden pb-16 md:pb-0">
            {/* Desktop tab bar inside MCP view */}
            {!isMobile && (
              <div className="w-full flex items-center justify-between px-4 sm:px-6 pt-3 pb-1 border-b border-[rgba(65,230,255,0.1)] bg-[rgba(4,9,15,0.5)]">
                <div className="flex items-center gap-2">
                  <button
                    onClick={toggleLeft}
                    title="Toggle Sensor Panel"
                    className={`p-1.5 rounded border text-[10px] font-mono flex items-center gap-1.5 transition-all ${
                      showLeftSidebar
                        ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                        : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                    }`}
                  >
                    <Sliders size={12} />
                    <span>SENSORS</span>
                  </button>

                  <div className="flex items-center gap-1 bg-[rgba(6,14,21,0.8)] p-1 rounded border border-[rgba(65,230,255,0.2)]">
                    <button
                      onClick={() => {
                        soundFx.click()
                        setCenterView('core')
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[10px] tracking-wider text-[#7da4b8] hover:text-[#e8fbff] transition-all"
                    >
                      <Radio size={11} />
                      <span>CORE HUD</span>
                    </button>
                    <button
                      onClick={() => {
                        soundFx.click()
                        setCenterView('mcp')
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[10px] tracking-wider bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold transition-all"
                    >
                      <Cpu size={11} className="text-[#41e6ff]" />
                      <span>MCP CONFIG</span>
                      <span className="size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_4px_#38ef7d]" />
                    </button>
                  </div>
                </div>

                <button
                  onClick={toggleRight}
                  title="Toggle Transmission Feed"
                  className={`p-1.5 rounded border text-[10px] font-mono flex items-center gap-1.5 transition-all ${
                    showRightSidebar
                      ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                      : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                  }`}
                >
                  <MessageSquare size={12} />
                  <span>LOGS</span>
                </button>
              </div>
            )}

            <McpConfigPanel
              onSendPrompt={handlePromptFromMcp}
              onClose={isMobile ? () => switchMobileTab('core') : undefined}
            />
          </main>
        ) : (
          (!isMobile || mobileTab === 'core') && (
            <main className="flex min-w-0 flex-1 flex-col items-center justify-between p-2.5 sm:p-4 md:p-5 overflow-y-auto space-y-3 sm:space-y-4 pb-20 md:pb-5 touch-scroll">
              {/* Top banner controls (Desktop only) */}
              <div className="w-full flex items-center justify-between max-w-4xl px-1 sm:px-2">
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <button
                    onClick={toggleLeft}
                    title="Toggle Sensor Panel"
                    className={`p-1.5 rounded border text-[10px] sm:text-[11px] font-mono hidden md:flex items-center gap-1.5 transition-all ${
                      showLeftSidebar
                        ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                        : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                    }`}
                  >
                    <Sliders size={12} />
                    <span>SENSORS</span>
                  </button>

                  <button
                    onClick={toggleScanlines}
                    title="Toggle CRT Scanline Filter"
                    className={`p-1.5 rounded border text-[10px] sm:text-[11px] font-mono flex items-center gap-1.5 transition-all ${
                      scanlinesActive
                        ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                        : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                    }`}
                  >
                    {scanlinesActive ? <Eye size={12} /> : <EyeOff size={12} />}
                    <span className="hidden xs:inline">SCANLINES</span>
                  </button>
                </div>

                {/* Deck Tab Switcher (Desktop only) */}
                <div className="hidden md:flex items-center gap-1 bg-[rgba(6,14,21,0.7)] p-1 rounded-lg border border-[rgba(65,230,255,0.2)]">
                  <button
                    onClick={() => {
                      soundFx.click()
                      setCenterView('core')
                    }}
                    className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold transition-all"
                  >
                    <Radio size={11} />
                    <span>CORE HUD</span>
                  </button>
                  <button
                    onClick={() => {
                      soundFx.click()
                      setCenterView('mcp')
                    }}
                    className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider text-[#7da4b8] hover:text-[#e8fbff] hover:bg-[rgba(65,230,255,0.08)] transition-all"
                  >
                    <Cpu size={11} className="text-[#41e6ff]" />
                    <span>MCP MODULES</span>
                    <span className="size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_4px_#38ef7d]" />
                  </button>
                </div>

                <button
                  onClick={toggleRight}
                  title="Toggle Transmission Feed"
                  className={`p-1.5 rounded border text-[10px] sm:text-[11px] font-mono hidden md:flex items-center gap-1.5 transition-all ${
                    showRightSidebar
                      ? 'border-[#41e6ff] text-[#41e6ff] bg-[rgba(65,230,255,0.1)]'
                      : 'border-[rgba(65,230,255,0.2)] text-[#7da4b8] bg-[rgba(6,14,21,0.6)]'
                  }`}
                >
                  <MessageSquare size={12} />
                  <span>LOGS</span>
                </button>
              </div>

              {/* Core Orb & Reactor Display */}
              <div className="flex flex-col items-center justify-center my-auto py-1 sm:py-2">
                <CoreOrb size={isMobile ? 140 : 190} phase={activePhase} online={connected} />

                {/* Dynamic Phase Display */}
                <div className="text-center mt-2 sm:mt-3">
                  <div
                    className={`font-display text-xl sm:text-2xl md:text-3xl font-bold tracking-[0.28em] sm:tracking-[0.35em] transition-colors duration-500 ${
                      !connected
                        ? 'text-[#ff5d5d]'
                        : activePhase === 'speaking'
                          ? 'text-[#ffc24b] drop-shadow-[0_0_12px_rgba(255,194,75,0.6)]'
                          : activePhase === 'processing'
                            ? 'text-[#ba68ff] drop-shadow-[0_0_12px_rgba(186,104,255,0.6)]'
                            : activePhase === 'listening'
                              ? 'text-[#41e6ff] drop-shadow-[0_0_15px_rgba(65,230,255,0.8)]'
                              : 'text-[#e8fbff] drop-shadow-[0_0_12px_rgba(65,230,255,0.5)]'
                    }`}
                  >
                    {connected ? activePhase.toUpperCase() : 'OFFLINE'}
                    <span className="cursor-blink ml-1" aria-hidden />
                  </div>
                  <div className="mt-1 font-mono text-[9.5px] sm:text-[10.5px] md:text-xs tracking-[0.18em] sm:tracking-[0.22em] text-[#7da4b8] px-2 max-w-sm sm:max-w-none truncate">
                    {connected ? phaseLabel : 'START ASSISTANT BACKEND: ./run.sh'}
                  </div>
                </div>
              </div>

              {/* Lower Control Stack (Visualizer + Gauges + WakeMeter + Terminal Deck) */}
              <div className="w-full max-w-2xl space-y-2.5 sm:space-y-3">
                {/* Audio Waveform Oscilloscope */}
                <AudioWaveform
                  phase={activePhase}
                  online={connected}
                  wakeScore={activeSnap.wake_score}
                  noiseFloor={snap.noise_floor}
                />

                {/* Wake Word Sensitivity Meter */}
                <WakeMeter
                  score={activeSnap.wake_score}
                  threshold={snap.threshold}
                  noiseFloor={snap.noise_floor}
                />

                {/* 4-Column Quick Telemetry Gauges */}
                <TelemetryGauges snap={activeSnap} connected={connected} />

                {/* Interactive Terminal Uplink Input & Push-To-Talk Button */}
                <CommandDeck
                  onSend={sendPrompt}
                  onPtt={triggerPtt}
                  phase={activePhase}
                  connected={connected}
                  onVoiceStateChange={setWebListening}
                />
              </div>
            </main>
          )
        )}

        {/* Right Transmission & Telemetry Feed (Desktop sidebar or Mobile Tab) */}
        {((!isMobile && showRightSidebar) || (isMobile && mobileTab === 'logs')) && (
          <FeedPanel
            snap={activeSnap}
            logs={logs}
            onClearLogs={clearLogs}
            onClose={isMobile ? () => switchMobileTab('core') : undefined}
          />
        )}
      </div>

      {/* Cyberpunk Mobile Bottom Navigation Bar (3 items: MCP Config [Left] | Core HUD [Center] | Feed Logs [Right]) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around h-14 bg-[rgba(4,9,15,0.95)] border-t border-[rgba(65,230,255,0.2)] backdrop-blur-lg pb-safe px-4 shadow-[0_-4px_20px_rgba(0,0,0,0.5)]">
        {/* Left: MCP MODULES */}
        <button
          onClick={() => switchMobileTab('mcp')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'mcp'
              ? 'text-[#41e6ff] drop-shadow-[0_0_10px_rgba(65,230,255,0.8)] scale-105'
              : 'text-[#7da4b8] opacity-70 hover:opacity-100'
          }`}
        >
          <div className="relative flex items-center justify-center">
            <Cpu size={19} className={mobileTab === 'mcp' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'} />
            <span className="absolute -top-0.5 -right-1 size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_4px_#38ef7d]" />
          </div>
          <span className="font-mono text-[9px] tracking-wider mt-0.5 font-bold">MCP CONFIG</span>
        </button>

        {/* Center: CORE HUD */}
        <button
          onClick={() => switchMobileTab('core')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'core'
              ? 'text-[#41e6ff] drop-shadow-[0_0_12px_rgba(65,230,255,0.9)] scale-105'
              : 'text-[#7da4b8] opacity-70 hover:opacity-100'
          }`}
        >
          <div className={`p-1 rounded-full border ${mobileTab === 'core' ? 'border-[#41e6ff] bg-[rgba(65,230,255,0.2)] shadow-[0_0_8px_rgba(65,230,255,0.4)]' : 'border-transparent'}`}>
            <Radio size={19} />
          </div>
          <span className="font-mono text-[9px] tracking-wider mt-0.5 font-bold">CORE HUD</span>
        </button>

        {/* Right: FEED LOGS */}
        <button
          onClick={() => switchMobileTab('logs')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'logs'
              ? 'text-[#41e6ff] drop-shadow-[0_0_10px_rgba(65,230,255,0.8)] scale-105'
              : 'text-[#7da4b8] opacity-70 hover:opacity-100'
          }`}
        >
          <MessageSquare size={19} className={mobileTab === 'logs' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'} />
          <span className="font-mono text-[9px] tracking-wider mt-0.5 font-semibold">FEED LOGS</span>
        </button>
      </nav>
    </div>
  )
}

