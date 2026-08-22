import { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import {
  Terminal as TerminalIcon,
  X,
  Maximize2,
  Minimize2,
  RefreshCw,
  Trash2,
  Keyboard,
  Cpu,
  Send,
  ArrowDown,
  Sparkles,
} from 'lucide-react'
import { soundFx } from '../lib/soundFx'

interface Props {
  isOpen: boolean
  onClose: () => void
}

type DockHeight = 'compact' | 'medium' | 'tall' | 'fullscreen'

const HEIGHT_MAP: Record<DockHeight, string> = {
  compact: 'h-64 sm:h-72',
  medium: 'h-80 sm:h-96',
  tall: 'h-[32rem] sm:h-[38rem]',
  fullscreen: 'h-[100dvh] sm:h-[calc(100vh-3.5rem)]',
}

const QUICK_COMMANDS = [
  { label: 'ls -la', cmd: 'ls -la' },
  { label: 'clear', cmd: 'clear' },
  { label: 'top', cmd: 'top' },
  { label: 'git status', cmd: 'git status' },
  { label: 'battery', cmd: 'termux-battery-status' },
  { label: 'torch on', cmd: 'termux-torch on' },
  { label: 'torch off', cmd: 'termux-torch off' },
  { label: 'pwd', cmd: 'pwd' },
  { label: 'whoami', cmd: 'whoami' },
  { label: 'df -h', cmd: 'df -h' },
  { label: 'uname -a', cmd: 'uname -a' },
  { label: 'exit', cmd: 'exit' },
]

export function IntegratedTerminal({ isOpen, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const mobileInputRef = useRef<HTMLInputElement>(null)

  const [connected, setConnected] = useState(false)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768)
  const [dockHeight, setDockHeight] = useState<DockHeight>(() => (typeof window !== 'undefined' && window.innerWidth < 768 ? 'fullscreen' : 'fullscreen'))
  const [shellInfo, setShellInfo] = useState<string>('TERMUX / LINUX SHELL')
  const [ctrlActive, setCtrlActive] = useState(false)
  const [altActive, setAltActive] = useState(false)
  const [showMobileKeys, setShowMobileKeys] = useState(true)
  const [showQuickChips, setShowQuickChips] = useState(true)
  const [commandInput, setCommandInput] = useState('')
  const [viewportHeight, setViewportHeight] = useState<number | null>(null)

  // Track window resize & mobile state
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (mobile) {
        setDockHeight('fullscreen')
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Visual Viewport tracking for mobile virtual soft keyboards
  useEffect(() => {
    if (!isOpen || typeof window === 'undefined' || !window.visualViewport) return

    const handleVisualViewportResize = () => {
      if (window.visualViewport) {
        setViewportHeight(window.visualViewport.height)
        if (fitAddonRef.current && xtermRef.current) {
          setTimeout(() => {
            try {
              fitAddonRef.current?.fit()
              xtermRef.current?.scrollToBottom()
              if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && xtermRef.current) {
                wsRef.current.send(
                  JSON.stringify({
                    type: 'resize',
                    cols: xtermRef.current.cols,
                    rows: xtermRef.current.rows,
                  })
                )
              }
            } catch {}
          }, 60)
        }
      }
    }

    window.visualViewport.addEventListener('resize', handleVisualViewportResize)
    window.visualViewport.addEventListener('scroll', handleVisualViewportResize)

    return () => {
      window.visualViewport?.removeEventListener('resize', handleVisualViewportResize)
      window.visualViewport?.removeEventListener('scroll', handleVisualViewportResize)
    }
  }, [isOpen])

  // Connect WebSocket
  const connectWebSocket = useCallback((term: Terminal, fitAddon: FitAddon) => {
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch {}
      wsRef.current = null
    }

    const host = window.location.hostname || 'localhost'
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${host}:2028`

    term.writeln('\x1b[1;36m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Connecting to Integrated Terminal on ' + wsUrl + '...')

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      term.writeln('\x1b[1;32m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Terminal bridge online. Auto-scroll active.\r\n')
      fitAddon.fit()
      term.scrollToBottom()
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
    }

    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        try {
          if (ev.data.startsWith('{') && ev.data.endsWith('}')) {
            const data = JSON.parse(ev.data)
            if (data.shell) setShellInfo(data.shell)
            return
          }
        } catch {}
        term.write(ev.data, () => {
          term.scrollToBottom()
        })
      } else {
        term.write(new Uint8Array(ev.data), () => {
          term.scrollToBottom()
        })
      }
    }

    ws.onerror = () => {
      setConnected(false)
      term.writeln('\r\n\x1b[1;31m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Connection to terminal bridge failed or disconnected.\x1b[0m')
      term.scrollToBottom()
    }

    ws.onclose = () => {
      setConnected(false)
      term.writeln('\r\n\x1b[1;33m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Session closed.\x1b[0m')
      term.scrollToBottom()
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
        term.scrollToBottom()
      }
    })
  }, [])

  // Initialize and manage xterm instance
  const initTerminal = useCallback(() => {
    if (!containerRef.current) return

    if (xtermRef.current) {
      try {
        xtermRef.current.dispose()
      } catch {}
      xtermRef.current = null
    }

    const isTouch = window.innerWidth < 768 || 'ontouchstart' in window

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'bar',
      fontFamily: '"Cascadia Mono", "SF Mono", "Fira Code", monospace',
      fontSize: isTouch ? 12 : 13,
      lineHeight: 1.2,
      scrollback: 5000,
      scrollOnUserInput: true,
      theme: {
        background: '#04090f',
        foreground: '#b3e8f7',
        cursor: '#41e6ff',
        cursorAccent: '#04090f',
        selectionBackground: 'rgba(65, 230, 255, 0.3)',
        black: '#000000',
        red: '#ff5d5d',
        green: '#41ff96',
        yellow: '#ffc24b',
        blue: '#4196ff',
        magenta: '#ba68ff',
        cyan: '#41e6ff',
        white: '#e8fbff',
        brightBlack: '#3e5c6d',
        brightRed: '#ff7e7e',
        brightGreen: '#72ffb4',
        brightYellow: '#ffd57d',
        brightBlue: '#73b2ff',
        brightMagenta: '#d095ff',
        brightCyan: '#7ef3ff',
        brightWhite: '#ffffff',
      },
      allowTransparency: true,
      convertEol: true,
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)

    term.open(containerRef.current)
    fitAddon.fit()
    term.scrollToBottom()

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    connectWebSocket(term, fitAddon)
  }, [connectWebSocket])

  // Mount/Unmount on isOpen
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        initTerminal()
      }, 50)
      return () => clearTimeout(timer)
    } else {
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch {}
        wsRef.current = null
      }
      if (xtermRef.current) {
        try {
          xtermRef.current.dispose()
        } catch {}
        xtermRef.current = null
      }
      setConnected(false)
    }
  }, [isOpen, initTerminal])

  // Resize observer to auto-fit terminal whenever container size changes
  useEffect(() => {
    if (!isOpen || !containerRef.current) return

    const observer = new ResizeObserver(() => {
      if (fitAddonRef.current && xtermRef.current) {
        try {
          fitAddonRef.current.fit()
          xtermRef.current.scrollToBottom()
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: 'resize',
                cols: xtermRef.current.cols,
                rows: xtermRef.current.rows,
              })
            )
          }
        } catch {}
      }
    })

    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [isOpen, dockHeight])

  // Send virtual key sequence (for touch & quick actions)
  const sendKey = (key: string) => {
    soundFx.click()
    const ws = wsRef.current
    const term = xtermRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    let payload = key
    if (ctrlActive) {
      setCtrlActive(false)
      const code = key.toUpperCase().charCodeAt(0)
      if (code >= 64 && code <= 95) {
        payload = String.fromCharCode(code - 64)
      }
    } else if (altActive) {
      setAltActive(false)
      payload = `\x1b${key}`
    }

    ws.send(payload)
    if (term) {
      term.scrollToBottom()
      term.focus()
    }
  }

  // Execute full command string directly
  const executeCommand = (cmdText: string) => {
    soundFx.click()
    const ws = wsRef.current
    const term = xtermRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN || !cmdText.trim()) return

    ws.send(cmdText.trim() + '\r')
    if (term) {
      term.scrollToBottom()
      term.focus()
    }
  }

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!commandInput.trim()) return
    executeCommand(commandInput)
    setCommandInput('')
  }

  const clearTerminal = () => {
    soundFx.click()
    if (xtermRef.current) {
      xtermRef.current.clear()
      xtermRef.current.scrollToBottom()
    }
  }

  const reconnect = () => {
    soundFx.click()
    if (xtermRef.current && fitAddonRef.current) {
      connectWebSocket(xtermRef.current, fitAddonRef.current)
    }
  }

  const cycleHeight = () => {
    soundFx.click()
    setDockHeight((prev) => {
      if (prev === 'compact') return 'medium'
      if (prev === 'medium') return 'tall'
      if (prev === 'tall') return 'fullscreen'
      return 'compact'
    })
  }

  const scrollToBottom = () => {
    soundFx.click()
    xtermRef.current?.scrollToBottom()
  }

  if (!isOpen) return null

  // Calculate dynamic container style for mobile visual viewport
  const containerStyle =
    isMobile && viewportHeight
      ? { height: `${viewportHeight}px`, maxHeight: `${viewportHeight}px` }
      : undefined

  const isFullscreen = dockHeight === 'fullscreen' || isMobile

  return (
    <div
      style={containerStyle}
      className={`fixed inset-x-0 ${
        isFullscreen ? 'inset-0 top-0 h-[100dvh]' : `bottom-0 ${HEIGHT_MAP[dockHeight]}`
      } bg-[#04090f]/98 border-t ${
        isFullscreen ? 'border-transparent' : 'border-[rgba(65,230,255,0.3)]'
      } backdrop-blur-2xl z-50 flex flex-col shadow-[0_-8px_32px_rgba(0,0,0,0.9),0_0_24px_rgba(65,230,255,0.15)] transition-all duration-200`}
    >
      {/* Top Header / Titlebar */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 bg-[rgba(9,20,29,0.95)] border-b border-[rgba(65,230,255,0.18)] select-none shrink-0">
        {/* Left: Identity & Shell */}
        <div className="flex items-center gap-2 sm:gap-3">
          <TerminalIcon className={`size-4 ${connected ? 'text-[#41e6ff] animate-pulse' : 'text-[#ff5d5d]'}`} />
          <div className="font-display text-xs sm:text-sm font-bold tracking-[0.2em] text-[#e8fbff] flex items-center gap-1.5">
            <span>ATHENA</span>
            <span className="text-[#41e6ff]">//</span>
            <span className="text-[#41e6ff]">TERMINAL</span>
          </div>

          <div className="hidden xs:flex items-center gap-1.5 px-2 py-0.5 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[10px] font-mono text-[#7da4b8]">
            <Cpu size={11} className="text-[#41e6ff]" />
            <span className="truncate max-w-[140px] sm:max-w-[220px]">{shellInfo}</span>
          </div>
        </div>

        {/* Right: Controls & Status */}
        <div className="flex items-center gap-1 sm:gap-2">
          {/* Connection status badge */}
          <div className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] sm:text-[10px] font-mono tracking-wider bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.15)]">
            <span
              className={`size-1.5 rounded-full ${connected ? 'bg-[#41ff96]' : 'bg-[#ff5d5d]'}`}
              style={{ boxShadow: connected ? '0 0 6px #41ff96' : '0 0 6px #ff5d5d' }}
            />
            <span className={connected ? 'text-[#41ff96]' : 'text-[#ff5d5d]'}>
              {connected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>

          {/* Quick Chips Toggle */}
          <button
            onClick={() => {
              soundFx.click()
              setShowQuickChips((p) => !p)
            }}
            title={showQuickChips ? 'Hide Quick Commands' : 'Show Quick Commands'}
            className={`p-1.5 rounded transition-colors ${
              showQuickChips
                ? 'text-[#41e6ff] bg-[rgba(65,230,255,0.15)]'
                : 'text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.08)]'
            }`}
          >
            <Sparkles size={13} />
          </button>

          {/* Virtual Keyboard Toggle */}
          <button
            onClick={() => {
              soundFx.click()
              setShowMobileKeys((p) => !p)
            }}
            title={showMobileKeys ? 'Hide Virtual Keys' : 'Show Virtual Keys'}
            className={`p-1.5 rounded transition-colors ${
              showMobileKeys
                ? 'text-[#41e6ff] bg-[rgba(65,230,255,0.15)]'
                : 'text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.08)]'
            }`}
          >
            <Keyboard size={13} />
          </button>

          {/* Quick Clear */}
          <button
            onClick={clearTerminal}
            title="Clear Terminal Display"
            className="p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
          >
            <Trash2 size={13} />
          </button>

          {/* Reconnect */}
          <button
            onClick={reconnect}
            title="Restart Session"
            className="p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
          >
            <RefreshCw size={13} />
          </button>

          {/* Height Toggle (Desktop only) */}
          {!isMobile && (
            <button
              onClick={cycleHeight}
              title={`Current: ${dockHeight.toUpperCase()} (Click to cycle)`}
              className="p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
            >
              {dockHeight === 'fullscreen' ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          )}

          {/* Close */}
          <button
            onClick={() => {
              soundFx.click()
              onClose()
            }}
            title="Close Integrated Terminal"
            className="p-1.5 text-[#7da4b8] hover:text-[#ff5d5d] hover:bg-[rgba(255,93,93,0.15)] rounded transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Quick Command Chips Strip */}
      {showQuickChips && (
        <div className="flex items-center px-2 py-1.5 bg-[rgba(6,14,21,0.92)] border-b border-[rgba(65,230,255,0.1)] overflow-x-auto no-scrollbar gap-1.5 shrink-0 select-none">
          <span className="font-mono text-[9px] text-[#7da4b8] uppercase tracking-wider px-1 shrink-0 flex items-center gap-1">
            <Sparkles size={10} className="text-[#41e6ff]" />
            QUICK:
          </span>
          {QUICK_COMMANDS.map((qc) => (
            <button
              key={qc.label}
              onClick={() => executeCommand(qc.cmd)}
              className="px-2.5 py-1 rounded-full bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.18)] active:scale-95 border border-[rgba(65,230,255,0.15)] hover:border-[#41e6ff] text-[11px] font-mono text-[#b3e8f7] hover:text-[#41e6ff] whitespace-nowrap transition-all"
            >
              {qc.label}
            </button>
          ))}
        </div>
      )}

      {/* Terminal Viewport */}
      <div className="flex-1 w-full bg-[#04090f] overflow-hidden select-text relative focus:outline-none min-h-0">
        <div
          ref={containerRef}
          className="w-full h-full p-2"
          onClick={() => xtermRef.current?.focus()}
        />

        {/* Floating Auto-Scroll Button */}
        <button
          onClick={scrollToBottom}
          title="Scroll to bottom"
          className="absolute bottom-3 right-4 p-2 rounded-full bg-[#09141d]/90 hover:bg-[#41e6ff]/20 border border-[rgba(65,230,255,0.3)] text-[#41e6ff] shadow-lg backdrop-blur-md transition-all active:scale-90"
        >
          <ArrowDown size={14} />
        </button>
      </div>

      {/* Direct Mobile Command Prompt Input Bar */}
      <form
        onSubmit={handleInputSubmit}
        className="flex items-center gap-1.5 px-2 py-1.5 bg-[rgba(6,14,21,0.98)] border-t border-[rgba(65,230,255,0.15)] shrink-0"
      >
        <div className="flex items-center gap-1 font-mono text-[#41e6ff] text-xs pl-1">
          <span>&gt;</span>
        </div>
        <input
          ref={mobileInputRef}
          type="text"
          value={commandInput}
          onChange={(e) => setCommandInput(e.target.value)}
          placeholder="Type terminal command (e.g. ls, top, pkg install)..."
          className="flex-1 bg-[rgba(3,7,11,0.8)] border border-[rgba(65,230,255,0.2)] focus:border-[#41e6ff] rounded px-2.5 py-1.5 text-xs font-mono text-[#e8fbff] placeholder-[#3e5c6d] outline-none transition-colors"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck="false"
        />
        <button
          type="submit"
          disabled={!commandInput.trim()}
          title="Send Command"
          className="px-3 py-1.5 rounded bg-[rgba(65,230,255,0.15)] hover:bg-[rgba(65,230,255,0.3)] active:scale-95 disabled:opacity-30 border border-[rgba(65,230,255,0.3)] text-[#41e6ff] font-mono text-xs flex items-center gap-1 transition-all"
        >
          <Send size={12} />
          <span className="hidden xs:inline">RUN</span>
        </button>
      </form>

      {/* Mobile / Touch Quick Key Toolbar (Large comfortable targets) */}
      {showMobileKeys && (
        <div className="flex items-center justify-between px-2 py-1.5 bg-[rgba(4,9,15,0.98)] border-t border-[rgba(65,230,255,0.12)] text-xs font-mono overflow-x-auto no-scrollbar gap-1 shrink-0 select-none pb-safe">
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('\x1b')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] active:text-[#41e6ff] text-[11px] font-semibold"
            >
              ESC
            </button>
            <button
              onClick={() => sendKey('\t')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] active:text-[#41e6ff] text-[11px] font-semibold"
            >
              TAB
            </button>
            <button
              onClick={() => {
                soundFx.click()
                setCtrlActive((p) => !p)
              }}
              className={`px-2.5 py-1.5 min-h-[34px] rounded border text-[11px] font-semibold transition-all ${
                ctrlActive
                  ? 'bg-[#41e6ff]/25 border-[#41e6ff] text-[#41e6ff] shadow-[0_0_10px_#41e6ff]'
                  : 'bg-[rgba(65,230,255,0.08)] border-[rgba(65,230,255,0.2)] text-[#b3e8f7]'
              }`}
            >
              CTRL
            </button>
            <button
              onClick={() => {
                soundFx.click()
                setAltActive((p) => !p)
              }}
              className={`px-2.5 py-1.5 min-h-[34px] rounded border text-[11px] font-semibold transition-all ${
                altActive
                  ? 'bg-[#ffc24b]/25 border-[#ffc24b] text-[#ffc24b] shadow-[0_0_10px_#ffc24b]'
                  : 'bg-[rgba(65,230,255,0.08)] border-[rgba(65,230,255,0.2)] text-[#b3e8f7]'
              }`}
            >
              ALT
            </button>
            <button
              onClick={() => sendKey('\x03')}
              title="Ctrl+C (Interrupt)"
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(255,93,93,0.15)] active:bg-[rgba(255,93,93,0.35)] border border-[rgba(255,93,93,0.35)] text-[#ff7e7e] text-[11px] font-bold"
            >
              ^C
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('|')}
              className="px-2 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              |
            </button>
            <button
              onClick={() => sendKey('/')}
              className="px-2 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              /
            </button>
            <button
              onClick={() => sendKey('-')}
              className="px-2 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              -
            </button>
            <button
              onClick={() => sendKey('~')}
              className="px-2 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              ~
            </button>
            <button
              onClick={() => sendKey('$')}
              className="px-2 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              $
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('\x1b[A')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              ▲
            </button>
            <button
              onClick={() => sendKey('\x1b[B')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              ▼
            </button>
            <button
              onClick={() => sendKey('\x1b[D')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              ◀
            </button>
            <button
              onClick={() => sendKey('\x1b[C')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[rgba(65,230,255,0.08)] active:bg-[rgba(65,230,255,0.25)] border border-[rgba(65,230,255,0.2)] text-[#b3e8f7] text-[11px]"
            >
              ▶
            </button>
            <button
              onClick={() => sendKey('\r')}
              className="px-2.5 py-1.5 min-h-[34px] rounded bg-[#41e6ff]/20 active:bg-[#41e6ff]/40 border border-[#41e6ff] text-[#41e6ff] text-[11px] font-bold"
            >
              ⏎
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
