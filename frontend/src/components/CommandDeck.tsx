import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import { Send, Terminal, Activity, CloudSun, GitBranch, ExternalLink, Mic, Radio, BookOpen, Sparkles } from 'lucide-react'

interface Props {
  onSend: (text: string) => Promise<boolean>
  onPtt?: (state: 'press' | 'release') => Promise<boolean>
  phase?: string
  disabled?: boolean
  connected: boolean
  onVoiceStateChange?: (active: boolean) => void
}

const QUICK_ACTIONS = [
  { label: 'Morning Briefing', query: 'Athena, give me my morning briefing with weather, tasks, and headlines.', icon: Sparkles },
  { label: 'Pomodoro 25m', query: 'Athena, set a Pomodoro focus timer for 25 minutes.', icon: Activity },
  { label: 'Evening Debrief', query: 'Athena, give me my evening debrief and recap.', icon: Sparkles },
  { label: 'Deep Research', query: 'Athena, run deep research on solid-state battery technology and breakthroughs.', icon: Sparkles },
  { label: 'System Status', query: 'What is the current system status, memory, and active window?', icon: Activity },
  { label: 'MCP Weather', query: 'Athena, what is the weather in Chennai, Tamil Nadu, India according to the MCP weather tool?', icon: CloudSun },
  { label: 'MCP Notes', query: 'Athena, list my saved notes and active tasks from memory.', icon: BookOpen },
  { label: 'Code Git Status', query: 'Athena, what is the git status and active branch in our project workspace?', icon: GitBranch },
  { label: 'Open in VS Code', query: 'Athena, open the application project in VS Code.', icon: ExternalLink },
]

export const CommandDeck = memo(function CommandDeck({
  onSend,
  phase,
  disabled,
  connected,
  onVoiceStateChange,
}: Props) {
  const [text, setText] = useState('')
  const [transmitting, setTransmitting] = useState(false)
  const [isHolding, setIsHolding] = useState(false)
  const recognitionRef = useRef<any>(null)
  const speechTextRef = useRef<string>('')
  const isHoldingRef = useRef<boolean>(false)

  // Clean up recognition instance on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {}
      }
    }
  }, [])

  const startHoldVoice = useCallback(() => {
    if (!connected || disabled || transmitting || isHoldingRef.current) return

    const SpeechRec =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRec) {
      alert(
        'Speech Recognition is not supported by this browser. Please use Google Chrome on Android or Safari on iOS.',
      )
      return
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch {}
      recognitionRef.current = null
    }

    try {
      soundFx.click()
      isHoldingRef.current = true
      setIsHolding(true)
      onVoiceStateChange?.(true)
      speechTextRef.current = ''
      setText('')

      const rec = new SpeechRec()
      rec.continuous = false
      rec.interimResults = true
      rec.lang = 'en-US'
      rec.maxAlternatives = 1

      rec.onresult = (event: any) => {
        let full = ''
        for (let i = 0; i < event.results.length; ++i) {
          const piece = event.results[i][0]?.transcript?.trim() || ''
          if (!piece) continue
          if (!full) {
            full = piece
          } else if (piece.toLowerCase().startsWith(full.toLowerCase())) {
            full = piece
          } else if (full.toLowerCase().endsWith(piece.toLowerCase())) {
            // Duplicate suffix: ignore
          } else {
            full = `${full} ${piece}`
          }
        }
        if (full) {
          speechTextRef.current = full
          setText(full)
        }
      }

      rec.onerror = (event: any) => {
        if (event.error === 'not-allowed') {
          alert('Microphone access blocked. Please allow microphone permissions in your mobile browser.')
        } else if (event.error !== 'no-speech') {
          console.debug('Speech recognition event:', event.error)
        }
      }

      rec.onend = () => {
        if (!isHoldingRef.current) {
          setIsHolding(false)
          onVoiceStateChange?.(false)
        }
      }

      recognitionRef.current = rec
      rec.start()
    } catch (err) {
      console.error('Failed to start speech recognition:', err)
      isHoldingRef.current = false
      setIsHolding(false)
      onVoiceStateChange?.(false)
    }
  }, [connected, disabled, transmitting, onVoiceStateChange])

  const stopHoldVoice = useCallback(async () => {
    if (!isHoldingRef.current) return
    isHoldingRef.current = false
    setIsHolding(false)
    onVoiceStateChange?.(false)

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {}
    }

    // Small delay to allow any pending final onresult audio packet from browser
    await new Promise((r) => setTimeout(r, 60))

    const promptToSend = speechTextRef.current.trim() || text.trim()
    if (promptToSend && !transmitting && connected) {
      setTransmitting(true)
      await onSend(promptToSend)
      setText('')
      speechTextRef.current = ''
      setTransmitting(false)
    }
  }, [text, transmitting, connected, onSend, onVoiceStateChange])

  // Unified Pointer Handlers for Mobile Touch + Desktop Mouse
  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    startHoldVoice()
  }

  const handlePointerUp = (e: React.PointerEvent) => {
    e.preventDefault()
    stopHoldVoice()
  }

  // Desktop Spacebar Hotkey
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (e.code === 'Space' && !e.repeat && tag !== 'input' && tag !== 'textarea') {
        e.preventDefault()
        startHoldVoice()
      }
    }
    const handleKeyUp = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (e.code === 'Space' && tag !== 'input' && tag !== 'textarea') {
        e.preventDefault()
        stopHoldVoice()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [startHoldVoice, stopHoldVoice])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (isHolding) {
      await stopHoldVoice()
      return
    }
    const trimmed = text.trim()
    if (!trimmed || transmitting || disabled || !connected) return

    setTransmitting(true)
    setText('')
    speechTextRef.current = ''
    await onSend(trimmed)
    setTransmitting(false)
  }

  const handleChipClick = async (query: string) => {
    soundFx.click()
    if (transmitting || disabled || !connected) return
    setTransmitting(true)
    await onSend(query)
    setTransmitting(false)
  }

  const isListening = phase === 'listening' || isHolding

  return (
    <div className="w-full space-y-2.5">
      {/* 1. Hold-To-Talk Voice Button (Unified Pointer Events) */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onPointerLeave={isHolding ? handlePointerUp : undefined}
          disabled={!connected || disabled}
          className={`flex-1 py-2.5 sm:py-3 px-4 rounded font-display text-[11px] sm:text-xs tracking-[0.2em] sm:tracking-[0.25em] font-bold flex items-center justify-center gap-2 transition-all select-none touch-none active:scale-[0.98] ${
            isHolding
              ? 'bg-[#41e6ff] text-[#03070b] shadow-[0_0_25px_#41e6ff] animate-pulse border border-[#7ef3ff]'
              : isListening
                ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.4)]'
                : 'bg-[rgba(6,14,21,0.85)] text-[#7ef3ff] hover:text-[#e8fbff] border border-[rgba(65,230,255,0.3)] hover:border-[#41e6ff] hover:bg-[rgba(65,230,255,0.12)]'
          } disabled:opacity-40 disabled:pointer-events-none`}
        >
          {isHolding ? (
            <>
              <Radio size={15} className="animate-spin text-[#03070b]" />
              <span>RECORDING VOICE... RELEASE TO TRANSMIT</span>
            </>
          ) : (
            <>
              <Mic size={15} className="text-[#41e6ff]" />
              <span>HOLD TO TALK // PUSH-TO-TALK</span>
            </>
          )}
        </button>
      </div>

      {/* 2. Quick Action Chips */}
      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar touch-scroll py-1 sm:flex-wrap">
        <span className="font-mono text-[9px] uppercase tracking-widest text-[#7da4b8] flex items-center gap-1 mr-1 shrink-0">
          <Terminal size={11} className="text-[#41e6ff]" /> Quick:
        </span>
        {QUICK_ACTIONS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.label}
              onClick={() => handleChipClick(item.query)}
              disabled={!connected || transmitting}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10.5px] sm:text-[11px] font-mono tracking-wider text-[#7ef3ff] bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.15)] border border-[rgba(65,230,255,0.22)] hover:border-[rgba(65,230,255,0.5)] rounded transition-all shrink-0 disabled:opacity-30 disabled:pointer-events-none active:scale-95 touch-manipulation"
            >
              <Icon size={10} className="text-[#41e6ff]" />
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>

      {/* 3. Clean Terminal Input Bay */}
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <div className="absolute left-3.5 text-[#41e6ff] pointer-events-none flex items-center gap-1">
          <span className="font-mono text-xs font-bold">&gt;</span>
        </div>

        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            isHolding
              ? 'Listening to speech... release to send...'
              : connected
                ? 'Type command or hold button above to speak...'
                : 'Assistant offline — start backend: ./run.sh'
          }
          disabled={!connected || transmitting}
          className={`w-full pl-8 pr-28 py-2.5 font-mono text-xs tracking-wider bg-[rgba(6,14,21,0.85)] border ${
            isHolding
              ? 'border-[#41e6ff] shadow-[0_0_15px_rgba(65,230,255,0.35)] text-white'
              : 'border-[rgba(65,230,255,0.25)] text-[#e8fbff]'
          } focus:border-[#41e6ff] focus:ring-1 focus:ring-[#41e6ff] focus:outline-none rounded placeholder-[#3e5c6d] shadow-[inset_0_0_12px_rgba(0,0,0,0.5)] transition-all disabled:opacity-40`}
        />

        <button
          type="submit"
          disabled={!connected || !text.trim() || transmitting}
          className="absolute right-1.5 px-3 py-1.5 font-display text-[10px] tracking-[0.18em] text-[#041018] bg-[#41e6ff] hover:bg-[#7ef3ff] disabled:bg-[#1d4a5c] disabled:text-[#7da4b8] rounded font-semibold transition-all flex items-center gap-1.5 shadow-[0_0_10px_rgba(65,230,255,0.4)] disabled:shadow-none active:scale-95 touch-manipulation"
        >
          <span>{transmitting ? 'SENDING' : 'TRANSMIT'}</span>
          <Send size={11} />
        </button>
      </form>
    </div>
  )
})
