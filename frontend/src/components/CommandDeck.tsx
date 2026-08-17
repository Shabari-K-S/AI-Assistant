import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import { Send, Terminal, Activity, Cpu, CloudSun, Dices, GitBranch, FolderSearch, ExternalLink, Mic } from 'lucide-react'

interface Props {
  onSend: (text: string) => Promise<boolean>
  onPtt?: (state: 'press' | 'release') => Promise<boolean>
  phase?: string
  disabled?: boolean
  connected: boolean
}

const QUICK_ACTIONS = [
  { label: 'System Status', query: 'What is the current system status, memory, and active window?', icon: Activity },
  { label: 'CPU & Load', query: 'Check CPU utilization and load average.', icon: Cpu },
  { label: 'Code Git Status', query: 'Sara, what is the git status and active branch in our project workspace?', icon: GitBranch },
  { label: 'Code Search', query: 'Sara, search the codebase for where MCPManager is defined.', icon: FolderSearch },
  { label: 'Open in VS Code', query: 'Sara, open the application project in VS Code.', icon: ExternalLink },
  { label: 'MCP Weather', query: 'Sara, what is the weather in Tokyo according to the MCP weather tool?', icon: CloudSun },
  { label: 'MCP Dice', query: 'Sara, roll two 20-sided dice via the MCP tool.', icon: Dices },
]

export const CommandDeck = memo(function CommandDeck({
  onSend,
  onPtt,
  phase,
  disabled,
  connected,
}: Props) {
  const [text, setText] = useState('')
  const [transmitting, setTransmitting] = useState(false)
  const [isPttActive, setIsPttActive] = useState(false)
  const recognitionRef = useRef<any>(null)

  // Initialize browser Web Speech API for mobile Android / iOS speech recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SpeechRecognition) {
      try {
        const rec = new SpeechRecognition()
        rec.continuous = false
        rec.interimResults = true
        rec.lang = 'en-US'

        rec.onresult = (event: any) => {
          let transcript = ''
          for (let i = 0; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript
          }
          if (transcript) {
            setText(transcript)
          }
        }

        rec.onerror = () => {
          // ignore benign errors like no-speech
        }

        recognitionRef.current = rec
      } catch {}
    }
  }, [])

  const handlePttPress = useCallback(() => {
    if (!connected || disabled || !onPtt) return
    setIsPttActive(true)
    onPtt('press')
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start()
      } catch {}
    }
  }, [connected, disabled, onPtt])

  const handlePttRelease = useCallback(() => {
    if (!connected || disabled || !onPtt) return
    setIsPttActive(false)
    onPtt('release')
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {}
    }
  }, [connected, disabled, onPtt])

  // Optional Spacebar hold-to-talk in browser when outside input fields
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (e.code === 'Space' && !e.repeat && tag !== 'input' && tag !== 'textarea') {
        e.preventDefault()
        handlePttPress()
      }
    }
    const handleKeyUp = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (e.code === 'Space' && tag !== 'input' && tag !== 'textarea') {
        e.preventDefault()
        handlePttRelease()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [handlePttPress, handlePttRelease])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || transmitting || disabled || !connected) return

    setTransmitting(true)
    setText('')
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

  const isListening = phase === 'listening' || isPttActive

  return (
    <div className="w-full space-y-2.5">
      {/* 1. Push-To-Talk (Hold-To-Talk) Voice Button */}
      {onPtt && (
        <div className="w-full">
          <button
            type="button"
            onMouseDown={handlePttPress}
            onMouseUp={handlePttRelease}
            onMouseLeave={isPttActive ? handlePttRelease : undefined}
            onTouchStart={handlePttPress}
            onTouchEnd={handlePttRelease}
            onTouchCancel={handlePttRelease}
            disabled={!connected || disabled}
            className={`w-full py-2.5 sm:py-3 px-4 rounded font-display text-[11px] sm:text-xs tracking-[0.2em] sm:tracking-[0.25em] font-bold flex items-center justify-center gap-2 transition-all select-none touch-none active:scale-[0.98] ${
              isPttActive
                ? 'bg-[#41e6ff] text-[#03070b] shadow-[0_0_20px_#41e6ff] animate-pulse border border-[#7ef3ff]'
                : isListening
                  ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.4)]'
                  : 'bg-[rgba(6,14,21,0.85)] text-[#7ef3ff] hover:text-[#e8fbff] border border-[rgba(65,230,255,0.3)] hover:border-[#41e6ff] hover:bg-[rgba(65,230,255,0.12)]'
            } disabled:opacity-40 disabled:pointer-events-none`}
          >
            <Mic
              size={15}
              className={isPttActive ? 'animate-bounce text-[#03070b]' : 'text-[#41e6ff]'}
            />
            <span>
              {isPttActive
                ? 'RECORDING VOICE... RELEASE TO TRANSMIT'
                : 'HOLD TO TALK // PUSH-TO-TALK'}
            </span>
          </button>
        </div>
      )}

      {/* 2. Quick Action Chips (Horizontally swipeable on mobile, wraps on larger screens) */}
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

      {/* 3. Terminal Input Bay */}
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <div className="absolute left-3.5 text-[#41e6ff] pointer-events-none flex items-center gap-1">
          <span className="font-mono text-xs font-bold">&gt;</span>
        </div>

        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            connected
              ? 'Enter command, tap Hold-To-Talk, or say "Sara..."'
              : 'Assistant offline — start backend: ./run.sh'
          }
          disabled={!connected || transmitting}
          className="w-full pl-8 pr-28 py-2.5 font-mono text-xs tracking-wider bg-[rgba(6,14,21,0.85)] border border-[rgba(65,230,255,0.25)] focus:border-[#41e6ff] focus:ring-1 focus:ring-[#41e6ff] focus:outline-none rounded text-[#e8fbff] placeholder-[#3e5c6d] shadow-[inset_0_0_12px_rgba(0,0,0,0.5)] transition-all disabled:opacity-40"
        />

        <button
          type="submit"
          disabled={!connected || !text.trim() || transmitting}
          className="absolute right-1.5 px-3 py-1.5 font-display text-[10px] tracking-[0.18em] text-[#041018] bg-[#41e6ff] hover:bg-[#7ef3ff] disabled:bg-[#1d4a5c] disabled:text-[#7da4b8] rounded font-semibold transition-all flex items-center gap-1.5 shadow-[0_0_10px_rgba(65,230,255,0.4)] disabled:shadow-none active:scale-95"
        >
          <span>{transmitting ? 'SENDING' : 'TRANSMIT'}</span>
          <Send size={11} />
        </button>
      </form>
    </div>
  )
})
