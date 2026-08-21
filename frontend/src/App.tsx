import { useState, useEffect, useCallback, useRef } from 'react'
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
import { NotesVaultPanel } from './components/NotesVaultPanel'
import { CyberReconPanel } from './components/CyberReconPanel'
import { ActiveTimersBar } from './components/ActiveTimersBar'
import { BriefingModal } from './components/BriefingModal'
import { useAssistant } from './hooks/useAssistant'
import { useTimers } from './hooks/useTimers'
import { soundFx } from './lib/soundFx'
import { Sliders, MessageSquare, Eye, EyeOff, Radio, Cpu, Sparkles, BookOpen, Sun, Shield } from 'lucide-react'

const PHASE_TAG: Record<string, string> = {
  standby: 'AWAITING WAKE WORD OR COMMAND',
  listening: 'RECEIVING VOICE SIGNAL — SPEAK YOUR QUERY',
  processing: 'SYNTHESIZING REASONING & TOOLS',
  speaking: 'STREAMING AUDIO TRANSMISSION',
}

type MobileTab = 'notes' | 'core' | 'cyber' | 'mcp' | 'logs'
type CenterView = 'core' | 'notes' | 'cyber' | 'mcp'

export default function App() {
  const {
    snap,
    logs,
    researchState,
    connected,
    setThreshold,
    setMuted,
    sendPrompt,
    triggerPtt,
    clearLogs,
  } = useAssistant()

  const {
    timers,
    createTimer,
    cancelTimer,
    briefing,
    setBriefing,
    loadingBriefing,
    fetchBriefing,
  } = useTimers()
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [scanlinesActive, setScanlinesActive] = useState(true)
  const [webListening, setWebListeningState] = useState(false)
  const webListeningTimerRef = useRef<any>(null)

  const setWebListening = useCallback((active: boolean) => {
    if (webListeningTimerRef.current) {
      clearTimeout(webListeningTimerRef.current)
      webListeningTimerRef.current = null
    }
    setWebListeningState(active)
    if (active) {
      // Hard fallback: never let UI stay stuck in listening for more than 4.0 seconds
      webListeningTimerRef.current = setTimeout(() => {
        setWebListeningState(false)
      }, 4000)
    }
  }, [])

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

  const handlePromptFromSubviews = (text: string) => {
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

      {/* Active Timers & Pomodoro Bar */}
      <ActiveTimersBar
        timers={timers}
        onCreateTimer={createTimer}
        onCancelTimer={cancelTimer}
      />

      {/* Briefing Modal */}
      {briefing && (
        <BriefingModal
          briefing={briefing}
          onClose={() => setBriefing(null)}
          onSendPrompt={handlePromptFromSubviews}
        />
      )}

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

        {/* Center View 1: Notes Vault Repository */}
        {(!isMobile && centerView === 'notes') || (isMobile && mobileTab === 'notes') ? (
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden p-2.5 sm:p-4 md:p-5 pb-20 md:pb-5">
            {/* Desktop Top Tab Navigation */}
            {!isMobile && (
              <div className="w-full flex items-center justify-between pb-3 mb-2 border-b border-[rgba(65,230,255,0.1)]">
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

                  {/* Desktop Center Switcher */}
                  <div className="flex items-center gap-1 bg-[rgba(6,14,21,0.8)] p-1 rounded-lg border border-[rgba(65,230,255,0.2)]">
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
                        setCenterView('notes')
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[10px] tracking-wider bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold transition-all"
                    >
                      <BookOpen size={11} className="text-[#41e6ff]" />
                      <span>NOTES VAULT</span>
                    </button>
                    <button
                      onClick={() => {
                        soundFx.click()
                        setCenterView('mcp')
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[10px] tracking-wider text-[#7da4b8] hover:text-[#e8fbff] transition-all"
                    >
                      <Cpu size={11} className="text-[#41e6ff]" />
                      <span>MCP MODULES</span>
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

            <div className="flex-1 min-h-0">
              <NotesVaultPanel onSendPrompt={handlePromptFromSubviews} />
            </div>
          </main>
        ) : (!isMobile && centerView === 'cyber') || (isMobile && mobileTab === 'cyber') ? (
          /* Center View: Cyber Recon & DAST Matrix */
          <main className="flex min-w-0 flex-1 flex-col overflow-y-auto p-4 md:p-6 pb-20 md:pb-6 space-y-4">
            <CyberReconPanel onSend={handlePromptFromSubviews} disabled={!connected} />
          </main>
        ) : (!isMobile && centerView === 'mcp') || (isMobile && mobileTab === 'mcp') ? (
          /* Center View 2: MCP Configuration Panel */
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
                        setCenterView('notes')
                      }}
                      className="flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[10px] tracking-wider text-[#7da4b8] hover:text-[#e8fbff] transition-all"
                    >
                      <BookOpen size={11} className="text-[#41e6ff]" />
                      <span>NOTES VAULT</span>
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
              onSendPrompt={handlePromptFromSubviews}
              onClose={isMobile ? () => switchMobileTab('core') : undefined}
            />
          </main>
        ) : (
          /* Center View 3: Primary Core HUD & Visualizer */
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
                      setCenterView('notes')
                    }}
                    className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider transition-all ${
                      centerView === 'notes'
                        ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold'
                        : 'text-[#7da4b8] hover:text-[#e8fbff] hover:bg-[rgba(65,230,255,0.08)]'
                    }`}
                  >
                    <BookOpen size={11} className="text-[#41e6ff]" />
                    <span>NOTES VAULT</span>
                  </button>
                  <button
                    onClick={() => {
                      soundFx.click()
                      setCenterView('cyber')
                    }}
                    className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider transition-all ${
                      centerView === 'cyber'
                        ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold'
                        : 'text-[#7da4b8] hover:text-[#e8fbff] hover:bg-[rgba(65,230,255,0.08)]'
                    }`}
                  >
                    <Shield size={11} className="text-cyan-400" />
                    <span>CYBER RECON</span>
                  </button>
                  <button
                    onClick={() => {
                      soundFx.click()
                      setCenterView('mcp')
                    }}
                    className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider transition-all ${
                      centerView === 'mcp'
                        ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[rgba(65,230,255,0.4)] shadow-[0_0_8px_rgba(65,230,255,0.3)] font-bold'
                        : 'text-[#7da4b8] hover:text-[#e8fbff] hover:bg-[rgba(65,230,255,0.08)]'
                    }`}
                  >
                    <Cpu size={11} className="text-[#41e6ff]" />
                    <span>MCP MODULES</span>
                    <span className="size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_4px_#38ef7d]" />
                  </button>
                  <button
                    onClick={() => fetchBriefing('morning')}
                    disabled={loadingBriefing}
                    className="flex items-center gap-1 px-2 py-1 rounded font-mono text-[9px] sm:text-[10px] tracking-wider bg-[rgba(255,194,75,0.15)] text-[#ffc24b] border border-[rgba(255,194,75,0.3)] hover:bg-[rgba(255,194,75,0.25)] transition-all font-bold"
                    title="Generate Daily Intelligence Briefing"
                  >
                    <Sun size={11} className={loadingBriefing ? 'animate-spin' : ''} />
                    <span>{loadingBriefing ? 'BRIEFING...' : 'BRIEFING'}</span>
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
                    {connected ? (snap.active_tool ? `RUNNING: ${snap.active_tool.name.toUpperCase()}` : activePhase.toUpperCase()) : 'OFFLINE'}
                    <span className="cursor-blink ml-1" aria-hidden />
                  </div>
                  <div className="mt-1 font-mono text-[9.5px] sm:text-[10.5px] md:text-xs tracking-[0.18em] sm:tracking-[0.22em] text-[#7da4b8] px-2 max-w-sm sm:max-w-none truncate">
                    {connected ? (snap.active_tool ? `⚡ MCP Tool Executing: ${snap.active_tool.name}` : phaseLabel) : 'START ASSISTANT BACKEND: ./run.sh'}
                  </div>
                </div>
              </div>

              {/* Lower Control Stack (Visualizer + Gauges + WakeMeter + Terminal Deck) */}
              <div className="w-full max-w-2xl space-y-2.5 sm:space-y-3">
                {/* Active Deep Research Background Task Card */}
                {researchState.active && (
                  <div className="w-full p-2.5 sm:p-3 rounded-lg bg-[rgba(186,104,255,0.12)] border border-[rgba(186,104,255,0.4)] shadow-[0_0_15px_rgba(186,104,255,0.25)] flex items-center justify-between animate-pulse">
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 rounded-md bg-[rgba(186,104,255,0.2)] text-[#ba68ff]">
                        <Sparkles size={16} />
                      </div>
                      <div>
                        <div className="font-mono text-[10px] sm:text-[11px] font-bold text-[#ba68ff] tracking-wider">
                          AUTONOMOUS DEEP RESEARCH ACTIVE: {researchState.topic?.toUpperCase()}
                        </div>
                        <div className="font-mono text-[9px] sm:text-[10px] text-[#e8fbff] opacity-80 mt-0.5">
                          Step {researchState.step ?? 1}/{researchState.total ?? 4}: {researchState.stage}
                        </div>
                      </div>
                    </div>
                    <span className="size-2 rounded-full bg-[#ba68ff] shadow-[0_0_6px_#ba68ff]" />
                  </div>
                )}

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

                {/* System Telemetry Gauges */}
                <TelemetryGauges snap={activeSnap} connected={connected} />

                {/* Command & Push-to-Talk Deck */}
                <CommandDeck
                  onSend={sendPrompt}
                  onPtt={triggerPtt}
                  phase={activePhase}
                  disabled={!connected}
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

      {/* Cyberpunk Mobile Bottom Navigation Bar (5 items: NOTES [1] | MCP [2] | CORE [3 - CENTER] | CYBER [4] | LOGS [5]) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around h-16 bg-gradient-to-t from-[#03060c] via-[#060c16]/95 to-[#060c16]/90 border-t border-[rgba(65,230,255,0.22)] backdrop-blur-2xl pb-safe px-3 shadow-[0_-8px_32px_rgba(0,0,0,0.75)]">
        {/* 1. NOTES VAULT */}
        <button
          onClick={() => switchMobileTab('notes')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'notes'
              ? 'text-[#41e6ff] drop-shadow-[0_0_10px_rgba(65,230,255,0.9)] scale-105 font-bold'
              : 'text-[#7da4b8] opacity-75 hover:opacity-100'
          }`}
        >
          <BookOpen size={18} className={mobileTab === 'notes' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'} />
          <span className="font-mono text-[8.5px] tracking-wider mt-1 font-bold">NOTES</span>
        </button>

        {/* 2. MCP MODULES (Left of Core) */}
        <button
          onClick={() => switchMobileTab('mcp')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'mcp'
              ? 'text-[#41e6ff] drop-shadow-[0_0_10px_rgba(65,230,255,0.9)] scale-105 font-bold'
              : 'text-[#7da4b8] opacity-75 hover:opacity-100'
          }`}
        >
          <div className="relative flex items-center justify-center">
            <Cpu size={18} className={mobileTab === 'mcp' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'} />
            <span className="absolute -top-0.5 -right-1 size-1.5 rounded-full bg-[#38ef7d] shadow-[0_0_5px_#38ef7d]" />
          </div>
          <span className="font-mono text-[8.5px] tracking-wider mt-1 font-bold">MCP</span>
        </button>

        {/* 3. CORE HUD (PROMINENT CENTER REACTOR) */}
        <button
          onClick={() => switchMobileTab('core')}
          className="flex-1 flex flex-col items-center justify-center -mt-3.5 transition-all group"
        >
          <div
            className={`size-12 rounded-full flex items-center justify-center border transition-all shadow-xl ${
              mobileTab === 'core'
                ? 'bg-gradient-to-tr from-[#0a2540] to-[#0d3b66] border-[#41e6ff] text-[#41e6ff] shadow-[0_0_20px_rgba(65,230,255,0.6)] scale-110'
                : 'bg-gradient-to-tr from-[#06101c] to-[#0a1c2e] border-[rgba(65,230,255,0.35)] text-[#7da4b8] hover:border-[#41e6ff] hover:text-[#41e6ff]'
            }`}
          >
            <Radio size={20} className={activePhase === 'speaking' || activePhase === 'listening' ? 'animate-pulse text-[#41e6ff]' : ''} />
          </div>
          <span className={`font-mono text-[8.5px] tracking-wider mt-1 font-bold ${mobileTab === 'core' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'}`}>
            CORE
          </span>
        </button>

        {/* 4. CYBER RECON (Right of Core) */}
        <button
          onClick={() => switchMobileTab('cyber')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'cyber'
              ? 'text-cyan-400 drop-shadow-[0_0_10px_rgba(65,230,255,0.9)] scale-105 font-bold'
              : 'text-[#7da4b8] opacity-75 hover:opacity-100'
          }`}
        >
          <Shield size={18} className={mobileTab === 'cyber' ? 'text-cyan-400' : 'text-[#7da4b8]'} />
          <span className="font-mono text-[8.5px] tracking-wider mt-1 font-bold">CYBER</span>
        </button>

        {/* 5. FEED LOGS */}
        <button
          onClick={() => switchMobileTab('logs')}
          className={`flex-1 flex flex-col items-center justify-center py-1 transition-all ${
            mobileTab === 'logs'
              ? 'text-[#41e6ff] drop-shadow-[0_0_10px_rgba(65,230,255,0.9)] scale-105 font-bold'
              : 'text-[#7da4b8] opacity-75 hover:opacity-100'
          }`}
        >
          <MessageSquare size={18} className={mobileTab === 'logs' ? 'text-[#41e6ff]' : 'text-[#7da4b8]'} />
          <span className="font-mono text-[8.5px] tracking-wider mt-1 font-bold">LOGS</span>
        </button>
      </nav>
    </div>
  )
}
