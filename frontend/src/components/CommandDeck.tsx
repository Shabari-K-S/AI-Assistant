import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import { Send, Terminal, Activity, Cpu, CloudSun, Dices, GitBranch, FolderSearch, ExternalLink, Mic, MicOff, Radio } from 'lucide-react'

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
  phase,
  disabled,
  connected,
}: Props) {
  const [text, setText] = useState('')
  const [transmitting, setTransmitting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const recognitionRef = useRef<any>(null)
  const speechTextRef = useRef<string>('')
  const manualStopRef = useRef<boolean>(false)

  // Clean up any ongoing recognition on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {}
      }
    }
  }, [])

  const startVoiceRecording = useCallback(() => {
    if (!connected || disabled || transmitting) return

    const SpeechRec =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRec) {
      alert(
        'Speech Recognition is not supported by this browser. Please use Chrome on Android or Safari on iOS.',
      )
      return
    }

    // Stop any existing instance
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch {}
    }

    try {
      soundFx.click()
      speechTextRef.current = ''
      manualStopRef.current = false
      setText('')

      const rec = new SpeechRec()
      rec.continuous = true
      rec.interimResults = true
      rec.lang = 'en-US'
      rec.maxAlternatives = 1

      rec.onstart = () => {
        setIsRecording(true)
      }

      rec.onresult = (event: any) => {
        let fullTranscript = ''
        for (let i = 0; i < event.results.length; i++) {
          fullTranscript += event.results[i][0].transcript
        }
        if (fullTranscript) {
          speechTextRef.current = fullTranscript
          setText(fullTranscript)
        }
      }

      rec.onerror = (event: any) => {
        if (event.error === 'not-allowed') {
          alert('Microphone access blocked. Please allow microphone permissions in your browser.')
        } else if (event.error !== 'no-speech') {
          console.debug('Speech recognition event:', event.error)
        }
        setIsRecording(false)
      }

      rec.onend = async () => {
        setIsRecording(false)
        const recorded = speechTextRef.current.trim()
        if (recorded) {
          setTransmitting(true)
          await onSend(recorded)
          setText('')
          speechTextRef.current = ''
          setTransmitting(false)
        }
      }

      recognitionRef.current = rec
      rec.start()
    } catch (err) {
      console.error('Failed to start speech recognition:', err)
      setIsRecording(false)
    }
  }, [connected, disabled, transmitting, onSend])

  const stopVoiceRecording = useCallback(() => {
    manualStopRef.current = true
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        setIsRecording(false)
      }
    } else {
      setIsRecording(false)
    }
  }, [])

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopVoiceRecording()
    } else {
      startVoiceRecording()
    }
  }, [isRecording, stopVoiceRecording, startVoiceRecording])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (isRecording) {
      stopVoiceRecording()
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

  const isListening = phase === 'listening' || isRecording

  return (
    <div className="w-full space-y-2.5">
      {/* 1. Voice Capture Bar: Tap-to-Talk or Hold-to-Talk */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleRecording}
          disabled={!connected || disabled}
          className={`flex-1 py-2.5 sm:py-3 px-4 rounded font-display text-[11px] sm:text-xs tracking-[0.2em] sm:tracking-[0.25em] font-bold flex items-center justify-center gap-2 transition-all select-none touch-manipulation active:scale-[0.98] ${
            isRecording
              ? 'bg-[#ff3b69] text-white shadow-[0_0_22px_#ff3b69] animate-pulse border border-[#ff7597]'
              : isListening
                ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.4)]'
                : 'bg-[rgba(6,14,21,0.85)] text-[#7ef3ff] hover:text-[#e8fbff] border border-[rgba(65,230,255,0.3)] hover:border-[#41e6ff] hover:bg-[rgba(65,230,255,0.12)]'
          } disabled:opacity-40 disabled:pointer-events-none`}
        >
          {isRecording ? (
            <>
              <Radio size={15} className="animate-spin text-white" />
              <span>RECORDING VOICE... TAP TO TRANSMIT</span>
            </>
          ) : (
            <>
              <Mic size={15} className="text-[#41e6ff]" />
              <span>VOICE PROMPT // TAP TO SPEAK</span>
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

      {/* 3. Terminal Input Bay with Integrated Mic and Transmit Buttons */}
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <div className="absolute left-3.5 text-[#41e6ff] pointer-events-none flex items-center gap-1">
          <span className="font-mono text-xs font-bold">&gt;</span>
        </div>

        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            isRecording
              ? 'Listening to speech... speak now...'
              : connected
                ? 'Type command, tap Mic, or speak into website...'
                : 'Assistant offline — start backend: ./run.sh'
          }
          disabled={!connected || transmitting}
          className={`w-full pl-8 pr-36 py-2.5 font-mono text-xs tracking-wider bg-[rgba(6,14,21,0.85)] border ${
            isRecording
              ? 'border-[#ff3b69] shadow-[0_0_15px_rgba(255,59,105,0.35)] text-white'
              : 'border-[rgba(65,230,255,0.25)] text-[#e8fbff]'
          } focus:border-[#41e6ff] focus:ring-1 focus:ring-[#41e6ff] focus:outline-none rounded placeholder-[#3e5c6d] shadow-[inset_0_0_12px_rgba(0,0,0,0.5)] transition-all disabled:opacity-40`}
        />

        <div className="absolute right-1.5 flex items-center gap-1.5">
          {/* Quick In-Input Mic Toggle */}
          <button
            type="button"
            onClick={toggleRecording}
            disabled={!connected || transmitting}
            title={isRecording ? 'Stop recording and transmit' : 'Speak command via microphone'}
            className={`p-1.5 rounded transition-all flex items-center justify-center ${
              isRecording
                ? 'bg-[#ff3b69] text-white shadow-[0_0_12px_#ff3b69] animate-pulse'
                : 'text-[#41e6ff] hover:text-[#e8fbff] bg-[rgba(65,230,255,0.1)] hover:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.3)]'
            } disabled:opacity-40 touch-manipulation`}
          >
            {isRecording ? <MicOff size={13} /> : <Mic size={13} />}
          </button>

          {/* Transmit Button */}
          <button
            type="submit"
            disabled={!connected || (!text.trim() && !isRecording) || transmitting}
            className="px-3 py-1.5 font-display text-[10px] tracking-[0.18em] text-[#041018] bg-[#41e6ff] hover:bg-[#7ef3ff] disabled:bg-[#1d4a5c] disabled:text-[#7da4b8] rounded font-semibold transition-all flex items-center gap-1.5 shadow-[0_0_10px_rgba(65,230,255,0.4)] disabled:shadow-none active:scale-95 touch-manipulation"
          >
            <span>{transmitting ? 'SENDING' : isRecording ? 'STOP & SEND' : 'TRANSMIT'}</span>
            <Send size={11} />
          </button>
        </div>
      </form>
    </div>
  )
})
