import { memo, useState, useEffect, useCallback, useRef } from 'react'
import { soundFx } from '../lib/soundFx'
import type { SlashCommand } from '../types'
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
  GraduationCap,
  Bot,
  Compass,
  Clock,
  Target,
  Trash2,
  HelpCircle,
  Zap,
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

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: '/learn',
    syntax: '/learn <url | topic | rules>',
    description: 'Learn new skill into .athena/skills/ from a doc URL, web search topic, or rules.',
    category: 'skills',
    icon: 'GraduationCap',
    example: '/learn https://docs.pwntools.com or /learn "GraphQL security testing"',
  },
  {
    command: '/skill',
    syntax: '/skill <list | show <name> | run <name>>',
    description: 'Inspect, list, and execute specialized skills from .athena/skills/.',
    category: 'skills',
    icon: 'Zap',
    example: '/skill list or /skill run ctf_exploit_playbook',
  },
  {
    command: '/agent',
    syntax: '/agent <list | dispatch <name> <task> | status | cancel <id>>',
    description: 'Dispatch specialized background sub-agents (recon, research, code, sysadmin, ctf).',
    category: 'agents',
    icon: 'Bot',
    example: '/agent dispatch recon_specialist 10.10.11.224',
  },
  {
    command: '/research',
    syntax: '/research <topic>',
    description: 'Autonomous multi-vector deep research across web sources with paper synthesis.',
    category: 'research',
    icon: 'Sparkles',
    example: '/research "Solid State Batteries 2026 breakthroughs"',
  },
  {
    command: '/recon',
    syntax: '/recon <target_ip_or_url>',
    description: 'Autonomous DAST security audit, sensitive file discovery, and vulnerability scan.',
    category: 'security',
    icon: 'ShieldCheck',
    example: '/recon 127.0.0.1 or /recon https://example.com',
  },
  {
    command: '/goal',
    syntax: '/goal <objective_statement>',
    description: 'Autonomous multi-step execution loop that keeps running until goal is completed.',
    category: 'core',
    icon: 'Target',
    example: '/goal Audit codebase for memory leaks and fix all lints',
  },
  {
    command: '/schedule',
    syntax: '/schedule <time/cron> <task>',
    description: 'Schedule one-shot voice reminders or recurring background tasks.',
    category: 'core',
    icon: 'Clock',
    example: '/schedule in 30 minutes "Review server logs"',
  },
  {
    command: '/briefing',
    syntax: '/briefing [morning | evening]',
    description: 'Generate daily intelligence report with live weather, tasks, and tech headlines.',
    category: 'core',
    icon: 'Compass',
    example: '/briefing morning',
  },
  {
    command: '/clear',
    syntax: '/clear',
    description: 'Clear terminal transcript history and reset HUD feed.',
    category: 'core',
    icon: 'Trash2',
    example: '/clear',
  },
  {
    command: '/help',
    syntax: '/help',
    description: 'Display interactive guide of all slash commands, skills, and agents.',
    category: 'core',
    icon: 'HelpCircle',
    example: '/help',
  },
]

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
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0)
  const [slashMenuOpen, setSlashMenuOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<any>(null)
  const speechTextRef = useRef<string>('')
  const isRecordingRef = useRef<boolean>(false)

  // Filtered slash commands list
  const filteredCommands = text.startsWith('/') && !text.includes(' ')
    ? SLASH_COMMANDS.filter((c) => c.command.toLowerCase().startsWith(text.trim().toLowerCase()) || text.trim() === '/')
    : []

  const showSlashMenu = slashMenuOpen && filteredCommands.length > 0

  useEffect(() => {
    if (text.startsWith('/') && !text.includes(' ')) {
      setSlashMenuOpen(true)
      setSelectedSlashIndex(0)
    } else {
      setSlashMenuOpen(false)
    }
  }, [text])

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
          } else if (piece.toLowerCase().endsWith(piece.toLowerCase())) {
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

  const handleToggleTapToTalk = useCallback(() => {
    if (isRecordingRef.current) {
      stopAndSendVoice()
    } else {
      startTapVoice()
    }
  }, [stopAndSendVoice, startTapVoice])

  const prevSignalRef = useRef(voiceToggleSignal ?? 0)
  useEffect(() => {
    if (voiceToggleSignal && voiceToggleSignal !== prevSignalRef.current) {
      prevSignalRef.current = voiceToggleSignal
      handleToggleTapToTalk()
    }
  }, [voiceToggleSignal, handleToggleTapToTalk])

  // Spacebar Hotkey (only when outside input)
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

  const selectSlashCommand = (cmd: SlashCommand) => {
    soundFx.click()
    setText(`${cmd.command} `)
    setSlashMenuOpen(false)
    inputRef.current?.focus()
  }

  // Keyboard navigation for slash commands
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSlashMenu) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedSlashIndex((prev) => (prev + 1) % filteredCommands.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedSlashIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length)
    } else if (e.key === 'Tab') {
      if (filteredCommands[selectedSlashIndex]) {
        e.preventDefault()
        selectSlashCommand(filteredCommands[selectedSlashIndex])
      }
    } else if (e.key === 'Enter') {
      if (text.trim() === '/' && filteredCommands[selectedSlashIndex]) {
        e.preventDefault()
        selectSlashCommand(filteredCommands[selectedSlashIndex])
      } else {
        setSlashMenuOpen(false)
      }
    } else if (e.key === 'Escape') {
      setSlashMenuOpen(false)
    }
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (isRecording) {
      await stopAndSendVoice()
      return
    }
    const trimmed = text.trim()
    if (!trimmed || transmitting || disabled || !connected) return

    setSlashMenuOpen(false)
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

  const renderCommandIcon = (iconName: string) => {
    switch (iconName) {
      case 'GraduationCap':
        return <GraduationCap size={14} className="text-[#ba68ff]" />
      case 'Zap':
        return <Zap size={14} className="text-[#41e6ff]" />
      case 'Bot':
        return <Bot size={14} className="text-[#818cf8]" />
      case 'Sparkles':
        return <Sparkles size={14} className="text-[#ba68ff]" />
      case 'ShieldCheck':
        return <ShieldCheck size={14} className="text-[#ff9900]" />
      case 'Target':
        return <Target size={14} className="text-[#ff3366]" />
      case 'Clock':
        return <Clock size={14} className="text-[#2ee59d]" />
      case 'Compass':
        return <Compass size={14} className="text-[#41e6ff]" />
      case 'Trash2':
        return <Trash2 size={14} className="text-[#ff5d5d]" />
      default:
        return <HelpCircle size={14} className="text-[#7da4b8]" />
    }
  }

  return (
    <div className="w-full space-y-2.5 relative">
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

        {/* Cancel Recording Button */}
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

      {/* 3. Floating Slash Commands Menu Popover */}
      {showSlashMenu && (
        <div className="absolute bottom-12 left-0 right-0 z-50 bg-[#060e15]/95 border border-[rgba(65,230,255,0.4)] rounded-xl shadow-[0_0_30px_rgba(65,230,255,0.25)] backdrop-blur-xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-150 max-h-72 overflow-y-auto divide-y divide-[rgba(65,230,255,0.1)]">
          <div className="px-3 py-1.5 bg-[rgba(65,230,255,0.1)] flex items-center justify-between font-mono text-[10px] text-[#7da4b8]">
            <span className="flex items-center gap-1.5 text-[#41e6ff] font-bold">
              <Zap size={12} /> ATHENA SLASH COMMANDS
            </span>
            <span>Tab / ↵ to insert • ↑↓ navigate • Esc close</span>
          </div>
          <div className="p-1 space-y-0.5">
            {filteredCommands.map((cmd, idx) => {
              const isSelected = idx === selectedSlashIndex
              return (
                <div
                  key={cmd.command}
                  onClick={() => selectSlashCommand(cmd)}
                  onMouseEnter={() => setSelectedSlashIndex(idx)}
                  className={`p-2 rounded-lg cursor-pointer transition-all flex items-start gap-2.5 ${
                    isSelected
                      ? 'bg-[rgba(65,230,255,0.18)] border border-[rgba(65,230,255,0.5)] shadow-[0_0_10px_rgba(65,230,255,0.2)]'
                      : 'hover:bg-[rgba(65,230,255,0.06)] border border-transparent'
                  }`}
                >
                  <div className="p-1 rounded bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] mt-0.5 shrink-0">
                    {renderCommandIcon(cmd.icon)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-[#41e6ff] tracking-wide">
                        {cmd.command}
                      </span>
                      <span className="font-mono text-[10px] text-[#ba68ff] opacity-80 truncate">
                        {cmd.syntax}
                      </span>
                    </div>
                    <p className="font-mono text-[10.5px] text-[#7da4b8] mt-0.5 leading-snug">
                      {cmd.description}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 4. Terminal Input Bay */}
      <form onSubmit={handleSubmit} className="relative flex items-center w-full">
        <div className="absolute left-3.5 text-[#41e6ff] pointer-events-none flex items-center gap-1">
          <span className="font-mono text-xs font-bold">&gt;</span>
        </div>

        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={
            isRecording
              ? 'Listening... Speak now and tap button (or press Enter) to send...'
              : connected
                ? 'Type / for slash commands or tap voice button above...'
                : 'Athena offline — run ./run.sh'
          }
          disabled={!connected || transmitting}
          className={`w-full pl-8 pr-28 sm:pr-32 py-2.5 font-mono text-xs tracking-wider bg-[rgba(6,14,21,0.85)] border ${
            isRecording
              ? 'border-[#41e6ff] shadow-[0_0_15px_rgba(65,230,255,0.35)] text-white'
              : showSlashMenu
                ? 'border-[#41e6ff] shadow-[0_0_15px_rgba(65,230,255,0.3)] text-[#e8fbff]'
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


