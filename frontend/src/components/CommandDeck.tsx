import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import { BRIDGE_URL } from '../types'
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
  { label: 'Morning Briefing', query: 'Sara, give me my morning briefing with weather, tasks, and headlines.', icon: Sparkles },
  { label: 'Pomodoro 25m', query: 'Sara, set a Pomodoro focus timer for 25 minutes.', icon: Activity },
  { label: 'Evening Debrief', query: 'Sara, give me my evening debrief and recap.', icon: Sparkles },
  { label: 'Deep Research', query: 'Sara, run deep research on solid-state battery technology and breakthroughs.', icon: Sparkles },
  { label: 'System Status', query: 'What is the current system status, memory, and active window?', icon: Activity },
  { label: 'MCP Weather', query: 'Sara, what is the weather in Chennai, Tamil Nadu, India according to the MCP weather tool?', icon: CloudSun },
  { label: 'MCP Notes', query: 'Sara, list my saved notes and active tasks from memory.', icon: BookOpen },
  { label: 'Code Git Status', query: 'Sara, what is the git status and active branch in our project workspace?', icon: GitBranch },
  { label: 'Open in VS Code', query: 'Sara, open the application project in VS Code.', icon: ExternalLink },
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
  const [handsFree, setHandsFree] = useState<boolean>(() => {
    return localStorage.getItem('sara_handsfree_wake') === 'true'
  })
  const [isWoken, setIsWoken] = useState(false)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const micStreamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const isHoldingRef = useRef<boolean>(false)
  const isWokenRef = useRef<boolean>(false)
  const isHandsFreeRecordingRef = useRef<boolean>(false)
  const silenceTimerRef = useRef<any>(null)

  // Toggle Hands-Free
  const toggleHandsFree = () => {
    soundFx.click()
    const next = !handsFree
    setHandsFree(next)
    localStorage.setItem('sara_handsfree_wake', String(next))
    if (!next) {
      cleanupAudio()
    }
  }

  const cleanupAudio = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop()
      } catch {}
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop())
      micStreamRef.current = null
    }
    if (audioCtxRef.current) {
      try {
        audioCtxRef.current.close()
      } catch {}
      audioCtxRef.current = null
    }
    setIsWoken(false)
    isWokenRef.current = false
    isHandsFreeRecordingRef.current = false
    setIsHolding(false)
    isHoldingRef.current = false
  }

  // Get or initialize silent mic stream (Zero Android Beeps)
  const getMicStream = async () => {
    if (!micStreamRef.current || !micStreamRef.current.active) {
      micStreamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    }
    return micStreamRef.current
  }

  // Transmit audio blob silently to /bridge/transcribe
  const sendAudioForTranscription = async (blob: Blob) => {
    if (blob.size < 1000) return
    setTransmitting(true)
    try {
      const reader = new FileReader()
      reader.onloadend = async () => {
        const base64Data = (reader.result as string).split(',')[1]
        if (!base64Data) {
          setTransmitting(false)
          return
        }

        try {
          const res = await fetch(`${BRIDGE_URL}/transcribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              audio_b64: base64Data,
              mime_type: blob.type || 'audio/webm',
            }),
          })
          const data = await res.json()
          if (data.ok && data.text) {
            setText(data.text)
            await onSend(data.text)
          }
        } catch (err) {
          console.error('Transcription upload failed:', err)
        } finally {
          setTransmitting(false)
          setIsWoken(false)
          isWokenRef.current = false
          onVoiceStateChange?.(false)
        }
      }
      reader.readAsDataURL(blob)
    } catch {
      setTransmitting(false)
    }
  }

  // 100% Silent Hold-to-Talk (Pure HTML5 MediaRecorder - Zero Android Beeps)
  const startHoldVoice = useCallback(async () => {
    if (!connected || disabled || transmitting || isHoldingRef.current) return

    try {
      isHoldingRef.current = true
      setIsHolding(true)
      onVoiceStateChange?.(true)
      audioChunksRef.current = []

      const stream = await getMicStream()
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }
      recorder.start(100)
      mediaRecorderRef.current = recorder
    } catch (err) {
      console.error('Failed to start silent mic recording:', err)
      setIsHolding(false)
      isHoldingRef.current = false
      onVoiceStateChange?.(false)
    }
  }, [connected, disabled, transmitting, onVoiceStateChange])

  const stopHoldVoice = useCallback(async () => {
    if (!isHoldingRef.current) return
    isHoldingRef.current = false
    setIsHolding(false)
    onVoiceStateChange?.(false)

    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state === 'inactive') return

    recorder.stop()
    await new Promise((r) => setTimeout(r, 120))

    if (audioChunksRef.current.length > 0) {
      const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' })
      audioChunksRef.current = []
      await sendAudioForTranscription(audioBlob)
    }
  }, [sendAudioForTranscription, onVoiceStateChange])

  // Silent Continuous Hands-Free VAD (Zero Android Beeps)
  useEffect(() => {
    if (!handsFree || !connected || disabled || isHolding) {
      cleanupAudio()
      return
    }

    if (phase === 'processing' || phase === 'speaking') {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        try {
          mediaRecorderRef.current.stop()
        } catch {}
      }
      isHandsFreeRecordingRef.current = false
      return
    }

    let isCancelled = false
    let animFrame: number | null = null

    const startSilentHandsFreeVAD = async () => {
      try {
        const stream = await getMicStream()
        if (isCancelled) return

        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
        const ctx = new AudioCtx()
        audioCtxRef.current = ctx

        const source = ctx.createMediaStreamSource(stream)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        source.connect(analyser)

        const dataArray = new Uint8Array(analyser.frequencyBinCount)

        let baselineNoise = 0.02
        let recordStartTime = 0
        let maxUtteranceTimer: any = null

        const startSpeechChunk = () => {
          if (isHandsFreeRecordingRef.current || phase !== 'standby' || isHoldingRef.current) return
          isHandsFreeRecordingRef.current = true
          recordStartTime = Date.now()
          setIsWoken(true)
          isWokenRef.current = true
          onVoiceStateChange?.(true)
          audioChunksRef.current = []

          try {
            navigator.vibrate?.([40, 30, 40])
          } catch {}

          const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/webm'

          const recorder = new MediaRecorder(stream, { mimeType })
          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
              audioChunksRef.current.push(e.data)
            }
          }
          recorder.start(100)
          mediaRecorderRef.current = recorder

          // Hard cap: max 4.5 seconds utterance so it NEVER gets stuck
          if (maxUtteranceTimer) clearTimeout(maxUtteranceTimer)
          maxUtteranceTimer = setTimeout(() => {
            finishSpeechChunk()
          }, 4500)
        }

        const finishSpeechChunk = async () => {
          if (!isHandsFreeRecordingRef.current) return
          isHandsFreeRecordingRef.current = false
          if (maxUtteranceTimer) clearTimeout(maxUtteranceTimer)
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
          silenceTimerRef.current = null

          const recorder = mediaRecorderRef.current
          if (recorder && recorder.state === 'recording') {
            recorder.stop()
            await new Promise((r) => setTimeout(r, 120))
            if (audioChunksRef.current.length > 0) {
              const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' })
              audioChunksRef.current = []
              await sendAudioForTranscription(audioBlob)
            }
          }
        }

        // Silent RMS Monitor with dynamic baseline tracking
        const checkRMS = () => {
          if (isCancelled) return
          analyser.getByteTimeDomainData(dataArray)
          let sum = 0
          for (let i = 0; i < dataArray.length; i++) {
            const val = (dataArray[i] - 128) / 128
            sum += val * val
          }
          const rms = Math.sqrt(sum / dataArray.length)

          if (!isHandsFreeRecordingRef.current) {
            baselineNoise = baselineNoise * 0.95 + rms * 0.05
            const triggerThreshold = Math.max(0.045, baselineNoise * 1.5 + 0.02)
            if (rms > triggerThreshold && phase === 'standby' && !isHoldingRef.current) {
              startSpeechChunk()
            }
          } else {
            const silenceThreshold = Math.max(0.035, baselineNoise * 1.25 + 0.01)
            if (rms < silenceThreshold) {
              if (!silenceTimerRef.current && Date.now() - recordStartTime > 800) {
                silenceTimerRef.current = setTimeout(() => {
                  finishSpeechChunk()
                }, 1000)
              }
            } else {
              if (silenceTimerRef.current) {
                clearTimeout(silenceTimerRef.current)
                silenceTimerRef.current = null
              }
            }
          }

          animFrame = requestAnimationFrame(checkRMS)
        }

        checkRMS()
      } catch (err) {
        console.warn('Hands-free VAD initialization failed:', err)
        setHandsFree(false)
        localStorage.setItem('sara_handsfree_wake', 'false')
      }
    }

    startSilentHandsFreeVAD()

    return () => {
      isCancelled = true
      if (animFrame) cancelAnimationFrame(animFrame)
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current)
      cleanupAudio()
    }
  }, [handsFree, connected, disabled, isHolding, phase])



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
      {/* 1. Hold-To-Talk Voice Button + Hands-Free "Hey S.A.R.A." Toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onPointerLeave={isHolding ? handlePointerUp : undefined}
          disabled={!connected || disabled}
          className={`flex-1 py-2.5 sm:py-3 px-3 sm:px-4 rounded font-display text-[11px] sm:text-xs tracking-[0.2em] sm:tracking-[0.25em] font-bold flex items-center justify-center gap-2 transition-all select-none touch-none active:scale-[0.98] ${
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
              <span>HOLD TO TALK</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={toggleHandsFree}
          disabled={!connected || disabled}
          title={handsFree ? 'Hands-Free Wake Word is Active (Say "Hey Sara")' : 'Click to enable Hands-Free "Hey Sara" Wake Word'}
          className={`py-2.5 sm:py-3 px-3 rounded font-display text-[10px] sm:text-[11px] tracking-wider font-semibold flex items-center gap-1.5 transition-all select-none shrink-0 border ${
            handsFree
              ? isWoken
                ? 'bg-[#34d399] text-[#03070b] border-[#34d399] shadow-[0_0_20px_#34d399] animate-bounce'
                : 'bg-[rgba(16,185,129,0.15)] text-[#34d399] border-[#34d399] shadow-[0_0_12px_rgba(16,185,129,0.3)]'
              : 'bg-[rgba(6,14,21,0.85)] text-[#7da4b8] border-[rgba(65,230,255,0.2)] hover:border-[#41e6ff] hover:text-[#41e6ff]'
          } disabled:opacity-40 disabled:pointer-events-none`}
        >
          <Radio size={14} className={handsFree ? 'animate-pulse text-[#34d399]' : 'text-[#7da4b8]'} />
          <span className="hidden sm:inline">
            {handsFree ? (isWoken ? 'HEY SARA: ACTIVE' : 'WAKE WORD ON') : 'HEY SARA: OFF'}
          </span>
          <span className="sm:hidden">
            {handsFree ? (isWoken ? 'SARA WOKE' : 'WAKE ON') : 'WAKE OFF'}
          </span>
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
