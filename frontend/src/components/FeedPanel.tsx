import { memo, useEffect, useRef, useState } from 'react'
import type { LogLine, Snapshot } from '../types'
import { soundFx } from '../lib/soundFx'
import { Copy, Check, Trash2, Radio, Bot, User, X } from 'lucide-react'

interface Props {
  snap: Snapshot
  logs: LogLine[]
  onClearLogs?: () => void
  onClose?: () => void
}

const LEVEL_COLOR: Record<string, string> = {
  INFO: 'text-[#7da4b8]',
  WARN: 'text-[#ffc24b]',
  ERROR: 'text-[#ff5d5d]',
}

const KIND_TAG: Record<LogLine['kind'], string> = {
  log: 'SYS',
  transcript: 'VOX',
  reply: 'SAR',
  error: 'ERR',
  command: 'CMD',
}

export const FeedPanel = memo(function FeedPanel({ snap, logs, onClearLogs, onClose }: Props) {
  const logRef = useRef<HTMLDivElement>(null)
  const [copiedTranscript, setCopiedTranscript] = useState(false)
  const [copiedReply, setCopiedReply] = useState(false)

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs.length])

  const copyText = (text: string, type: 'transcript' | 'reply') => {
    if (!text) return
    soundFx.click()
    navigator.clipboard.writeText(text).then(() => {
      if (type === 'transcript') {
        setCopiedTranscript(true)
        setTimeout(() => setCopiedTranscript(false), 1800)
      } else {
        setCopiedReply(true)
        setTimeout(() => setCopiedReply(false), 1800)
      }
    })
  }

  return (
    <aside className="flex w-full md:w-80 lg:w-[22rem] shrink-0 flex-col gap-3 overflow-y-auto border-l border-[rgba(65,230,255,0.14)] bg-[rgba(4,9,15,0.92)] md:bg-[rgba(4,9,15,0.6)] p-3 pb-20 md:pb-3">
      {/* Mobile-only header with close */}
      {onClose && (
        <div className="md:hidden flex items-center justify-between px-1 py-0.5 border-b border-[rgba(65,230,255,0.1)] mb-1">
          <span className="hud-label text-[10px] text-[#41e6ff]">TRANSMISSION FEED & LOGS</span>
          <button
            onClick={() => {
              soundFx.click()
              onClose()
            }}
            className="p-1 text-[#7da4b8] hover:text-[#41e6ff] rounded transition-colors"
            title="Close panel"
          >
            <X size={15} />
          </button>
        </div>
      )}
      {/* 1. Inbound Voice/Terminal Transcript */}
      <div className="hud-panel p-3.5 rounded relative">
        <div className="flex items-center justify-between mb-2">
          <div className="hud-label flex items-center gap-1.5 text-[9.5px]">
            <User size={12} className="text-[#41e6ff]" />
            <span>Inbound Transmission</span>
          </div>
          {snap.transcript && (
            <button
              onClick={() => copyText(snap.transcript, 'transcript')}
              title="Copy transcript"
              className="text-[#7da4b8] hover:text-[#41e6ff] p-1 rounded transition-colors"
            >
              {copiedTranscript ? <Check size={12} className="text-[#41e6ff]" /> : <Copy size={12} />}
            </button>
          )}
        </div>
        <p className="min-h-7 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-[#e8fbff]">
          {snap.transcript ? (
            <span>{snap.transcript}</span>
          ) : (
            <span className="text-[#3e5c6d] italic font-sans text-[11px]">NO SIGNAL — AWAITING VOICE OR COMMAND</span>
          )}
        </p>
      </div>

      {/* 2. S.A.R.A. Response */}
      <div className="hud-panel p-3.5 rounded relative">
        <div className="flex items-center justify-between mb-2">
          <div className="hud-label flex items-center gap-1.5 text-[9.5px]">
            <Bot size={12} className="text-[#7ef3ff]" />
            <span>S.A.R.A. Synthesis</span>
          </div>
          {snap.reply && (
            <button
              onClick={() => copyText(snap.reply, 'reply')}
              title="Copy response"
              className="text-[#7da4b8] hover:text-[#41e6ff] p-1 rounded transition-colors"
            >
              {copiedReply ? <Check size={12} className="text-[#41e6ff]" /> : <Copy size={12} />}
            </button>
          )}
        </div>
        <p className="min-h-7 whitespace-pre-wrap break-words text-xs leading-relaxed text-[#cdeef8]">
          {snap.reply ? (
            <span>{snap.reply}</span>
          ) : (
            <span className="text-[#3e5c6d] italic text-[11px]">STANDBY FOR GENERATION</span>
          )}
        </p>
      </div>

      {/* 3. Realtime Telemetry & Event Stream */}
      <div className="hud-panel p-3.5 rounded flex-1 flex flex-col min-h-64">
        <div className="flex items-center justify-between mb-2">
          <div className="hud-label flex items-center gap-1.5 text-[9.5px]">
            <Radio size={11} className="text-[#41e6ff]" />
            <span>Telemetry Stream ({logs.length})</span>
          </div>
          {onClearLogs && logs.length > 0 && (
            <button
              onClick={onClearLogs}
              title="Clear log"
              className="text-[#7da4b8] hover:text-[#ff5d5d] p-1 rounded transition-colors"
            >
              <Trash2 size={11} />
            </button>
          )}
        </div>

        <div
          ref={logRef}
          className="flex-1 overflow-y-auto pr-1 font-mono text-[10.5px] leading-relaxed max-h-72 select-text"
        >
          {logs.length === 0 ? (
            <p className="text-[#3e5c6d] italic text-[10px] mt-2">AWAITING EVENTS…</p>
          ) : (
            <ul className="space-y-1">
              {logs.map((l) => {
                const isErr = l.kind === 'error'
                const isTrans = l.kind === 'transcript'
                const isReply = l.kind === 'reply'
                const isCmd = l.kind === 'command'
                const color = isErr
                  ? 'text-[#ff5d5d]'
                  : isTrans
                    ? 'text-[#7ef3ff]'
                    : isReply
                      ? 'text-[#e8fbff]'
                      : isCmd
                        ? 'text-[#ba68ff]'
                        : LEVEL_COLOR[l.level ?? 'INFO'] ?? 'text-[#7da4b8]'

                return (
                  <li key={l.id} className={`border-b border-[rgba(65,230,255,0.05)] pb-0.5 ${color}`}>
                    <span className="mr-1.5 text-[#3e5c6d]">
                      [{new Date(l.t).toLocaleTimeString(undefined, { hour12: false })}]
                    </span>
                    <span className="mr-1.5 font-bold text-[9px] px-1 py-0.2 bg-[rgba(65,230,255,0.08)] rounded text-[#41e6ff]">
                      {KIND_TAG[l.kind] ?? 'LOG'}
                    </span>
                    {isCmd && (
                      <>
                        <span className="text-[#ba68ff] font-bold">&gt; </span>
                        <span>{l.text}</span>
                      </>
                    )}
                    {isTrans && (
                      <>
                        <span className="text-[#41e6ff]">“</span>
                        {l.text}
                        <span className="text-[#41e6ff]">”</span>
                        {l.confidence != null && (
                          <span className="text-[#3e5c6d] ml-1">({l.confidence.toFixed(2)})</span>
                        )}
                      </>
                    )}
                    {isReply && (
                      <>
                        <span className="text-[#e8fbff]">“</span>
                        {l.text}
                        <span className="text-[#e8fbff]">”</span>
                      </>
                    )}
                    {!isTrans && !isReply && !isCmd && (l.msg ?? l.text)}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </aside>
  )
})
