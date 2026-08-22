import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import {
  Send,
  Terminal,
  Activity,
  CloudSun,
  GitBranch,
  Mic,
  Radio,
  BookOpen,
  Sparkles,
  ShieldCheck,
  Wifi,
  Flashlight,
  Volume2,
  X,
  AudioWaveform,
} from 'lucide-react'

interface Props {
  onSend: (text: string) => Promise<boolean>
  onPtt?: (state: 'press' | 'release') => Promise<boolean>
  phase?: string
  disabled?: boolean
  connected: boolean
  onVoiceStateChange?: (active: boolean) => void
  voiceToggleSignal?: number
}

const QUICK_ACTIONS = [
  { label: 'Morning Briefing', query: 'Athena, give me my morning briefing with weather, tasks, and headlines.', icon: Sparkles },
  { label: 'Pomodoro 25m', query: 'Athena, set a Pomodoro focus timer for 25 minutes.', icon: Activity },
  { label: 'SSL Security Audit', query: 'Athena, inspect the SSL certificate, expiration date, and TLS security for google.com.', icon: ShieldCheck },
  { label: 'Wi-Fi Telemetry', query: 'Athena, check my Wi-Fi connection info, signal strength, and IP address.', icon: Wifi },
  { label: 'Torch Flashlight', query: 'Athena, toggle my flashlight on or off.', icon: Flashlight },
  { label: 'Device Volume', query: 'Athena, check and set the audio volume.', icon: Volume2 },
  { label: 'Deep Research', query: 'Athena, run deep research on solid-state battery technology and breakthroughs.', icon: Sparkles },
  { label: 'Code Git Status', query: 'Athena, what is the git status and active branch in our project workspace?', icon: GitBranch },
  { label: 'MCP Notes', query: 'Athena, list my saved notes and active tasks from memory.', icon: BookOpen },
  { label: 'MCP Weather', query: 'Athena, what is the weather in Chennai, Tamil Nadu, India according to the MCP weather tool?', icon: CloudSun },
]

export const CommandDeck = memo(function CommandDeck({
  onSend,
  phase,
  disabled,
  connected,
  onVoiceStateChange,
  voiceToggleSignal,
}: Props) {
  const [text, setText] = useState('')
  const [transmitting, setTransmitting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const recognitionRef = useRef<any>(null)
  const speechTextRef = useRef<string>('')
  const isRecordingRef = useRef<boolean>(false)

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

  const startTapVoice = useCallback(() => {
    if (!connected || disabled || transmitting || isRecordingRef.current) return

    const SpeechRec =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRec) {
      alert(
        'Speech Recognition is not supported by this browser. Please use Google Chrome or Safari.',
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
      isRecordingRef.current = true
      setIsRecording(true)
      onVoiceStateChange?.(true)
      speechTextRef.current = ''
      setText('')

      const rec = new SpeechRec()
      rec.continuous = true
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
          alert('Microphone access blocked. Please allow microphone permissions in your browser.')
          cancelTapVoice()
        } else if (event.error !== 'no-speech') {
          console.debug('Speech recognition event:', event.error)
        }
      }

      rec.onend = () => {
        // If continuous mode ended unexpectedly while still recording, restart
        if (isRecordingRef.current) {
          try {
            rec.start()
          } catch {}
        } else {
          setIsRecording(false)
          onVoiceStateChange?.(false)
        }
      }

      recognitionRef.current = rec
      rec.start()
    } catch (err) {
      console.error('Failed to start speech recognition:', err)
      isRecordingRef.current = false
      setIsRecording(false)
      onVoiceStateChange?.(false)
    }
  }, [connected, disabled, transmitting, onVoiceStateChange])

  const stopAndSendVoice = useCallback(async () => {
    if (!isRecordingRef.current) return
    isRecordingRef.current = false
    setIsRecording(false)
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
      soundFx.uplink()
      setTransmitting(true)
      await onSend(promptToSend)
      setText('')
      speechTextRef.current = ''
      setTransmitting(false)
    } else {
      soundFx.click()
      setText('')
      speechTextRef.current = ''
    }
  }, [text, transmitting, connected, onSend, onVoiceStateChange])

  const cancelTapVoice = useCallback(() => {
    isRecordingRef.current = false
    setIsRecording(false)
    onVoiceStateChange?.(false)
    soundFx.click()

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch {}
      recognitionRef.current = null
    }

    setText('')
    speechTextRef.current = ''
  }, [onVoiceStateChange])

  // Toggle Tap-to-Talk on button click
  const handleToggleTapToTalk = useCallback(() => {
    if (isRecordingRef.current) {
      stopAndSendVoice()
    } else {
      startTapVoice()
    }
  }, [stopAndSendVoice, startTapVoice])

  // External trigger signal (e.g. from tapping the Core Orb directly)
  const prevSignalRef = useRef(voiceToggleSignal ?? 0)
  useEffect(() => {
    if (voiceToggleSignal && voiceToggleSignal !== prevSignalRef.current) {
      prevSignalRef.current = voiceToggleSignal
      handleToggleTapToTalk()
    }
  }, [voiceToggleSignal, handleToggleTapToTalk])

  // Spacebar Hotkey: Tap spacebar once to start, tap again to send
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'textarea') return

      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault()
        if (isRecordingRef.current) {
          stopAndSendVoice()
        } else {
          startTapVoice()
        }
      } else if (e.code === 'Escape' && isRecordingRef.current) {
        e.preventDefault()
        cancelTapVoice()
      } else if (e.code === 'Enter' && isRecordingRef.current) {
        e.preventDefault()
        stopAndSendVoice()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [startTapVoice, stopAndSendVoice, cancelTapVoice])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (isRecording) {
      await stopAndSendVoice()
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
    if (isRecording) {
      cancelTapVoice()
    }
    setTransmitting(true)
    await onSend(query)
    setTransmitting(false)
  }

  const isListening = phase === 'listening' || isRecording

  return (
    <div className="w-full space-y-2.5">
      {/* 1. Tap-To-Talk Voice Button with Visual Feedback */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleToggleTapToTalk}
          disabled={!connected || disabled || transmitting}
          title={isRecording ? 'Tap to finish & transmit message (Space / Enter)' : 'Tap to start speaking (Space)'}
          className={`flex-1 py-2.5 sm:py-3 px-4 rounded font-display text-[11px] sm:text-xs tracking-[0.2em] sm:tracking-[0.25em] font-bold flex items-center justify-center gap-2.5 transition-all select-none cursor-pointer active:scale-[0.98] ${
            isRecording
              ? 'bg-[#41e6ff] text-[#03070b] shadow-[0_0_25px_#41e6ff] animate-pulse border border-[#7ef3ff]'
              : isListening
                ? 'bg-[rgba(65,230,255,0.2)] text-[#41e6ff] border border-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.4)]'
                : 'bg-[rgba(6,14,21,0.85)] text-[#7ef3ff] hover:text-[#e8fbff] border border-[rgba(65,230,255,0.3)] hover:border-[#41e6ff] hover:bg-[rgba(65,230,255,0.12)]'
          } disabled:opacity-40 disabled:pointer-events-none`}
        >
          {isRecording ? (
            <>
              <Radio size={16} className="text-[#03070b] animate-pulse" />
              <span>RECORDING VOICE... TAP TO SEND ⏎</span>
              <AudioWaveform size={14} className="text-[#03070b] animate-bounce ml-1" />
            </>
          ) : (
            <>
              <Mic size={16} className="text-[#41e6ff]" />
              <span>TAP TO TALK // VOICE TRANSMIT</span>
            </>
          )}
        </button>

        {/* Cancel Recording Button (Only visible while recording) */}
        {isRecording && (
          <button
            type="button"
            onClick={cancelTapVoice}
            title="Cancel voice recording (Esc)"
            className="px-3 py-2.5 sm:py-3 rounded bg-[rgba(255,93,93,0.15)] hover:bg-[rgba(255,93,93,0.3)] border border-[rgba(255,93,93,0.4)] text-[#ff7e7e] hover:text-white font-mono text-xs font-bold transition-all shadow-[0_0_8px_rgba(255,93,93,0.25)] flex items-center gap-1 shrink-0 cursor-pointer"
          >
            <X size={14} />
            <span className="hidden xs:inline">CANCEL</span>
          </button>
        )}
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
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10.5px] sm:text-[11px] font-mono tracking-wider text-[#7ef3ff] bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.15)] border border-[rgba(65,230,255,0.22)] hover:border-[rgba(65,230,255,0.5)] rounded transition-all shrink-0 disabled:opacity-30 disabled:pointer-events-none active:scale-95 touch-manipulation cursor-pointer"
            >
              <Icon size={10} className="text-[#41e6ff]" />
              <span>{item.label}</span>
            </button>
          )
        })}
      </div>

      {/* 3. Clean Terminal Input Bay */}
      <form onSubmit={handleSubmit} className="relative flex items-center w-full">
        <div className="absolute left-3.5 text-[#41e6ff] pointer-events-none flex items-center gap-1">
          <span className="font-mono text-xs font-bold">&gt;</span>
        </div>

        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            isRecording
              ? 'Listening... Speak now and tap button (or press Enter) to send...'
              : connected
                ? 'Type command or tap voice button above...'
                : 'Athena offline — run ./run.sh'
          }
          disabled={!connected || transmitting}
          className={`w-full pl-8 pr-28 sm:pr-32 py-2.5 font-mono text-xs tracking-wider bg-[rgba(6,14,21,0.85)] border ${
            isRecording
              ? 'border-[#41e6ff] shadow-[0_0_15px_rgba(65,230,255,0.35)] text-white'
              : 'border-[rgba(65,230,255,0.25)] text-[#e8fbff]'
          } focus:border-[#41e6ff] focus:ring-1 focus:ring-[#41e6ff] focus:outline-none rounded-lg placeholder-[#3e5c6d] shadow-[inset_0_0_12px_rgba(0,0,0,0.5)] transition-all disabled:opacity-40`}
        />

        <button
          type="submit"
          disabled={!connected || !text.trim() || transmitting}
          className="absolute right-1.5 px-3 py-1.5 font-display text-[10px] tracking-[0.18em] text-[#041018] bg-[#41e6ff] hover:bg-[#7ef3ff] disabled:bg-[#1d4a5c] disabled:text-[#7da4b8] rounded font-semibold transition-all flex items-center gap-1.5 shadow-[0_0_10px_rgba(65,230,255,0.4)] disabled:shadow-none active:scale-95 touch-manipulation shrink-0 cursor-pointer"
        >
          <span>{transmitting ? 'SENDING' : 'TRANSMIT'}</span>
          <Send size={11} />
        </button>
      </form>
    </div>
  )
})
