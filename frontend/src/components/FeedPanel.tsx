import { memo, useEffect, useRef, useState } from 'react'
import type { LogLine, Snapshot } from '../types'
import { soundFx } from '../lib/soundFx'
import { Copy, Check, Trash2, Radio, Bot, User, X, ChevronDown, ChevronRight, Wrench, Brain, Cpu } from 'lucide-react'

interface Props {
  snap: Snapshot
  logs: LogLine[]
  onClearLogs?: () => void
  onClose?: () => void
}

const KIND_TAG: Record<LogLine['kind'], { tag: string; bg: string; text: string }> = {
  log: { tag: 'SYS', bg: 'bg-[rgba(65,230,255,0.08)]', text: 'text-[#7da4b8]' },
  transcript: { tag: 'VOX', bg: 'bg-[rgba(65,230,255,0.15)]', text: 'text-[#41e6ff]' },
  reply: { tag: 'SAR', bg: 'bg-[rgba(126,243,255,0.15)]', text: 'text-[#7ef3ff]' },
  error: { tag: 'ERR', bg: 'bg-[rgba(255,93,93,0.15)]', text: 'text-[#ff5d5d]' },
  command: { tag: 'CMD', bg: 'bg-[rgba(186,104,255,0.15)]', text: 'text-[#ba68ff]' },
  tool: { tag: 'TOOL', bg: 'bg-[rgba(168,85,247,0.2)]', text: 'text-[#c084fc]' },
  memory: { tag: 'MEM', bg: 'bg-[rgba(16,185,129,0.2)]', text: 'text-[#34d399]' },
  llm: { tag: 'LLM', bg: 'bg-[rgba(245,158,11,0.2)]', text: 'text-[#fbbf24]' },
}

export const FeedPanel = memo(function FeedPanel({ snap, logs, onClearLogs, onClose }: Props) {
  const logRef = useRef<HTMLDivElement>(null)
  const [copiedTranscript, setCopiedTranscript] = useState(false)
  const [copiedReply, setCopiedReply] = useState(false)
  const [activeFilter, setActiveFilter] = useState<'all' | 'tool' | 'memory' | 'llm' | 'voice'>('all')
  const [expandedLogIds, setExpandedLogIds] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs.length, activeFilter])

  const toggleExpand = (id: string) => {
    soundFx.click()
    setExpandedLogIds((prev) => ({ ...prev, [id]: !prev[id] }))
  }

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

  const filteredLogs = logs.filter((l) => {
    if (activeFilter === 'all') return true
    if (activeFilter === 'tool') return l.kind === 'tool'
    if (activeFilter === 'memory') return l.kind === 'memory'
    if (activeFilter === 'llm') return l.kind === 'llm'
    if (activeFilter === 'voice') return l.kind === 'transcript' || l.kind === 'reply'
    return true
  })

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
      <div className="hud-panel p-3 rounded flex-1 flex flex-col min-h-72">
        <div className="flex items-center justify-between mb-2">
          <div className="hud-label flex items-center gap-1.5 text-[9.5px]">
            <Radio size={11} className="text-[#41e6ff]" />
            <span>Telemetry Feed ({filteredLogs.length})</span>
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

        {/* Filter Pills */}
        <div className="flex items-center gap-1 mb-2.5 pb-2 border-b border-[rgba(65,230,255,0.08)] overflow-x-auto text-[9px] font-mono">
          {(['all', 'tool', 'memory', 'llm', 'voice'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => {
                soundFx.click()
                setActiveFilter(filter)
              }}
              className={`px-1.5 py-0.5 rounded uppercase tracking-wider transition-colors ${
                activeFilter === filter
                  ? 'bg-[#41e6ff] text-[#04090f] font-bold shadow-[0_0_8px_rgba(65,230,255,0.4)]'
                  : 'bg-[rgba(65,230,255,0.06)] text-[#7da4b8] hover:text-[#41e6ff]'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        {/* Log Entries */}
        <div
          ref={logRef}
          className="flex-1 overflow-y-auto pr-1 font-mono text-[10px] leading-relaxed max-h-80 select-text space-y-1.5"
        >
          {filteredLogs.length === 0 ? (
            <p className="text-[#3e5c6d] italic text-[10px] mt-2">NO EVENTS MATCHING FILTER…</p>
          ) : (
            filteredLogs.map((l) => {
              const meta = KIND_TAG[l.kind] ?? KIND_TAG.log
              const isTool = l.kind === 'tool'
              const isMem = l.kind === 'memory'
              const isLlm = l.kind === 'llm'
              const isCmd = l.kind === 'command'
              const isTrans = l.kind === 'transcript'
              const isReply = l.kind === 'reply'
              const isExpanded = !!expandedLogIds[l.id]

              return (
                <div
                  key={l.id}
                  className="p-1.5 rounded bg-[rgba(9,20,29,0.6)] border border-[rgba(65,230,255,0.06)] hover:border-[rgba(65,230,255,0.2)] transition-colors"
                >
                  <div className="flex items-center justify-between text-[9px]">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[#3e5c6d]">
                        {new Date(l.t).toLocaleTimeString(undefined, { hour12: false })}
                      </span>
                      <span className={`font-bold px-1 py-0.2 rounded ${meta.bg} ${meta.text}`}>
                        {meta.tag}
                      </span>
                      {isTool && l.toolData?.duration_ms != null && (
                        <span className="text-[#34d399] font-bold bg-[rgba(16,185,129,0.1)] px-1 rounded">
                          {l.toolData.duration_ms}ms
                        </span>
                      )}
                      {isLlm && l.llmData?.ttft_ms != null && (
                        <span className="text-[#fbbf24] font-bold bg-[rgba(245,158,11,0.1)] px-1 rounded">
                          TTFT: {l.llmData.ttft_ms}ms
                        </span>
                      )}
                    </div>

                    {isTool && l.toolData?.args && (
                      <button
                        onClick={() => toggleExpand(l.id)}
                        className="text-[#c084fc] hover:text-[#e879f9] flex items-center gap-0.5 text-[8.5px]"
                      >
                        {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        <span>ARGS</span>
                      </button>
                    )}
                  </div>

                  {/* Main Log Content */}
                  <div className="mt-1 text-[#cdeef8] break-words">
                    {isTool && (
                      <div className="flex items-center gap-1 text-[#e879f9]">
                        <Wrench size={10} className="shrink-0 text-[#c084fc]" />
                        <span className="font-bold">{l.toolData?.name}</span>
                        {l.toolData?.status === 'running' ? (
                          <span className="text-[#ffc24b] text-[9px] animate-pulse">(running...)</span>
                        ) : (
                          <span className="text-[#7da4b8] text-[9px]">
                            {l.toolData?.preview ? `→ ${l.toolData.preview.slice(0, 70)}...` : '✓'}
                          </span>
                        )}
                      </div>
                    )}

                    {isMem && (
                      <div className="text-[#34d399]">
                        <div className="flex items-center gap-1 font-bold">
                          <Brain size={10} className="shrink-0" />
                          <span>Recall: {l.memoryData?.query || l.msg}</span>
                        </div>
                        {l.memoryData?.notes && l.memoryData.notes.length > 0 && (
                          <div className="mt-1 pl-3 space-y-0.5 text-[9px] text-[#7ef3ff]">
                            {l.memoryData.notes.map((n, idx) => (
                              <div key={idx}>
                                • [{n.title}] ({n.score ? `${Math.round(n.score * 100)}%` : 'match'})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {isLlm && (
                      <div className="flex items-center gap-1 text-[#fbbf24]">
                        <Cpu size={10} className="shrink-0" />
                        <span>
                          {l.llmData?.model} — Total: {l.llmData?.total_ms}ms ({l.llmData?.chars} chars)
                        </span>
                      </div>
                    )}

                    {isCmd && (
                      <div className="text-[#ba68ff]">
                        <span className="font-bold">&gt; </span>
                        <span>{l.text}</span>
                      </div>
                    )}

                    {isTrans && (
                      <div className="text-[#41e6ff]">
                        “{l.text}”
                        {l.confidence != null && (
                          <span className="text-[#3e5c6d] ml-1">({l.confidence.toFixed(2)})</span>
                        )}
                      </div>
                    )}

                    {isReply && (
                      <div className="text-[#e8fbff]">
                        “{l.text}”
                      </div>
                    )}

                    {!isTool && !isMem && !isLlm && !isCmd && !isTrans && !isReply && (
                      <span>{l.msg ?? l.text}</span>
                    )}
                  </div>

                  {/* Expandable JSON Arguments */}
                  {isTool && isExpanded && l.toolData?.args && (
                    <pre className="mt-1.5 p-1.5 rounded bg-[rgba(4,9,15,0.9)] text-[8.5px] text-[#c084fc] overflow-x-auto border border-[rgba(168,85,247,0.3)]">
                      {JSON.stringify(l.toolData.args, null, 2)}
                    </pre>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </aside>
  )
})
