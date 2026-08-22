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
  fullscreen: 'h-[calc(100vh-3.5rem)]',
}

export function IntegratedTerminal({ isOpen, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const [connected, setConnected] = useState(false)
  const [dockHeight, setDockHeight] = useState<DockHeight>('medium')
  const [shellInfo, setShellInfo] = useState<string>('TERMUX / LINUX SHELL')
  const [ctrlActive, setCtrlActive] = useState(false)
  const [altActive, setAltActive] = useState(false)
  const [showMobileKeys, setShowMobileKeys] = useState(true)

  // Initialize and manage xterm instance
  const initTerminal = useCallback(() => {
    if (!containerRef.current) return

    // Clean up previous instance if any
    if (xtermRef.current) {
      try {
        xtermRef.current.dispose()
      } catch {}
      xtermRef.current = null
    }

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'bar',
      fontFamily: '"Cascadia Mono", "SF Mono", "Fira Code", monospace',
      fontSize: 13,
      lineHeight: 1.25,
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

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    // Connect WebSocket
    connectWebSocket(term, fitAddon)
  }, [])

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

    term.writeln('\x1b[1;36m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Connecting to Integrated Terminal Bridge on ' + wsUrl + '...')

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      term.writeln('\x1b[1;32m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Terminal bridge session online. Press Ctrl+` to toggle.\r\n')
      fitAddon.fit()
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
        term.write(ev.data)
      } else {
        term.write(new Uint8Array(ev.data))
      }
    }

    ws.onerror = () => {
      setConnected(false)
      term.writeln('\r\n\x1b[1;31m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Connection to terminal bridge failed or disconnected.\x1b[0m')
    }

    ws.onclose = () => {
      setConnected(false)
      term.writeln('\r\n\x1b[1;33m[A.T.H.E.N.A. TELEMETRY]\x1b[0m Session closed.\x1b[0m')
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })
  }, [])

  // Mount/Unmount on isOpen
  useEffect(() => {
    if (isOpen) {
      // Small timeout to allow DOM to render container dimensions
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

  // Send virtual key sequence (for mobile & quick actions)
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
    if (term) term.focus()
  }

  const clearTerminal = () => {
    soundFx.click()
    if (xtermRef.current) {
      xtermRef.current.clear()
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

  if (!isOpen) return null

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 ${HEIGHT_MAP[dockHeight]} bg-[rgba(4,9,15,0.96)] border-t border-[rgba(65,230,255,0.3)] backdrop-blur-xl z-50 flex flex-col shadow-[0_-8px_32px_rgba(0,0,0,0.8),0_0_24px_rgba(65,230,255,0.12)] transition-all duration-200`}
    >
      {/* Top Header / Titlebar */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 bg-[rgba(9,20,29,0.9)] border-b border-[rgba(65,230,255,0.18)] select-none">
        {/* Left: Identity & Shell */}
        <div className="flex items-center gap-2 sm:gap-3">
          <TerminalIcon className={`size-4 ${connected ? 'text-[#41e6ff] animate-pulse' : 'text-[#ff5d5d]'}`} />
          <div className="font-display text-xs sm:text-sm font-bold tracking-[0.2em] text-[#e8fbff] flex items-center gap-1.5">
            <span>ATHENA</span>
            <span className="text-[#41e6ff]">//</span>
            <span className="text-[#41e6ff] hidden xs:inline">INTEGRATED TERMINAL</span>
            <span className="text-[#41e6ff] xs:hidden">SHELL</span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 px-2 py-0.5 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[10px] font-mono text-[#7da4b8]">
            <Cpu size={11} className="text-[#41e6ff]" />
            <span className="truncate max-w-[200px]">{shellInfo}</span>
          </div>
        </div>

        {/* Right: Controls & Status */}
        <div className="flex items-center gap-1 sm:gap-2">
          {/* Connection status badge */}
          <div className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] sm:text-[10px] font-mono tracking-wider bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.15)] mr-1">
            <span
              className={`size-1.5 rounded-full ${connected ? 'bg-[#41ff96]' : 'bg-[#ff5d5d]'}`}
              style={{ boxShadow: connected ? '0 0 6px #41ff96' : '0 0 6px #ff5d5d' }}
            />
            <span className={connected ? 'text-[#41ff96]' : 'text-[#ff5d5d]'}>
              {connected ? 'ONLINE' : 'DISCONNECTED'}
            </span>
          </div>

          {/* Toggle Virtual Key Toolbar */}
          <button
            onClick={() => {
              soundFx.click()
              setShowMobileKeys((p) => !p)
            }}
            title={showMobileKeys ? 'Hide Virtual Keys' : 'Show Virtual Keys'}
            className={`p-1 sm:p-1.5 rounded transition-colors ${
              showMobileKeys
                ? 'text-[#41e6ff] bg-[rgba(65,230,255,0.12)]'
                : 'text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.08)]'
            }`}
          >
            <Keyboard size={13} />
          </button>

          {/* Quick Clear */}
          <button
            onClick={clearTerminal}
            title="Clear Terminal Display"
            className="p-1 sm:p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
          >
            <Trash2 size={13} />
          </button>

          {/* Reconnect */}
          <button
            onClick={reconnect}
            title="Restart / Reconnect Session"
            className="p-1 sm:p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
          >
            <RefreshCw size={13} />
          </button>

          {/* Height Toggle */}
          <button
            onClick={cycleHeight}
            title={`Current: ${dockHeight.toUpperCase()} (Click to cycle)`}
            className="p-1 sm:p-1.5 text-[#7da4b8] hover:text-[#41e6ff] hover:bg-[rgba(65,230,255,0.1)] rounded transition-colors"
          >
            {dockHeight === 'fullscreen' ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>

          {/* Close */}
          <button
            onClick={() => {
              soundFx.click()
              onClose()
            }}
            title="Close Integrated Terminal (Ctrl+`)"
            className="p-1 sm:p-1.5 text-[#7da4b8] hover:text-[#ff5d5d] hover:bg-[rgba(255,93,93,0.12)] rounded transition-colors"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Terminal Canvas Viewport */}
      <div
        ref={containerRef}
        className="flex-1 w-full p-2 bg-[#04090f] overflow-hidden select-text relative focus:outline-none"
        onClick={() => xtermRef.current?.focus()}
      />

      {/* Mobile / Quick Action Key Toolbar */}
      {showMobileKeys && (
        <div className="flex items-center justify-between px-2 py-1 bg-[rgba(6,14,21,0.95)] border-t border-[rgba(65,230,255,0.12)] text-xs font-mono overflow-x-auto gap-1">
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('\x1b')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.15)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] hover:text-[#41e6ff] text-[10px]"
            >
              ESC
            </button>
            <button
              onClick={() => sendKey('\t')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.15)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] hover:text-[#41e6ff] text-[10px]"
            >
              TAB
            </button>
            <button
              onClick={() => {
                soundFx.click()
                setCtrlActive((p) => !p)
              }}
              className={`px-2 py-1 rounded border text-[10px] ${
                ctrlActive
                  ? 'bg-[#41e6ff]/20 border-[#41e6ff] text-[#41e6ff] shadow-[0_0_8px_#41e6ff]'
                  : 'bg-[rgba(65,230,255,0.06)] border-[rgba(65,230,255,0.15)] text-[#7da4b8]'
              }`}
            >
              CTRL
            </button>
            <button
              onClick={() => {
                soundFx.click()
                setAltActive((p) => !p)
              }}
              className={`px-2 py-1 rounded border text-[10px] ${
                altActive
                  ? 'bg-[#ffc24b]/20 border-[#ffc24b] text-[#ffc24b] shadow-[0_0_8px_#ffc24b]'
                  : 'bg-[rgba(65,230,255,0.06)] border-[rgba(65,230,255,0.15)] text-[#7da4b8]'
              }`}
            >
              ALT
            </button>
            <button
              onClick={() => sendKey('\x03')}
              title="Ctrl+C (Interrupt)"
              className="px-2 py-1 rounded bg-[rgba(255,93,93,0.1)] hover:bg-[rgba(255,93,93,0.25)] border border-[rgba(255,93,93,0.3)] text-[#ff7e7e] text-[10px]"
            >
              ^C
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('|')}
              className="px-1.5 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              |
            </button>
            <button
              onClick={() => sendKey('-')}
              className="px-1.5 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              -
            </button>
            <button
              onClick={() => sendKey('~')}
              className="px-1.5 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              ~
            </button>
            <button
              onClick={() => sendKey('/')}
              className="px-1.5 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              /
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => sendKey('\x1b[A')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              ▲
            </button>
            <button
              onClick={() => sendKey('\x1b[B')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              ▼
            </button>
            <button
              onClick={() => sendKey('\x1b[D')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              ◀
            </button>
            <button
              onClick={() => sendKey('\x1b[C')}
              className="px-2 py-1 rounded bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] text-[10px]"
            >
              ▶
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
