import { useState } from 'react'
import {
  Sun,
  Moon,
  Cloud,
  CheckCircle2,
  ListTodo,
  Newspaper,
  Cpu,
  Volume2,
  Copy,
  Check,
  X,
  ExternalLink,
} from 'lucide-react'
import type { DailyBriefing } from '../types'
import { soundFx } from '../lib/soundFx'

interface Props {
  briefing: DailyBriefing
  onClose: () => void
  onSendPrompt: (prompt: string) => Promise<boolean> | Promise<void> | void
}

export function BriefingModal({ briefing, onClose, onSendPrompt }: Props) {
  const [copied, setCopied] = useState(false)
  const isMorning = briefing.type === 'morning'

  const handleCopy = () => {
    soundFx.click()
    navigator.clipboard.writeText(briefing.markdown_report)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleReadAloud = async () => {
    soundFx.uplink()
    const prompt = isMorning
      ? 'Athena, please give me my morning briefing aloud.'
      : 'Athena, please give me my evening debrief aloud.'
    await onSendPrompt(prompt)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-6 bg-[#03070b]/90 backdrop-blur-xl animate-in fade-in duration-200">
      <div className="w-full max-w-3xl max-h-[90vh] bg-[#060e15] border border-[rgba(65,230,255,0.3)] rounded-2xl flex flex-col shadow-[0_0_40px_rgba(65,230,255,0.2)] overflow-hidden">
        {/* Modal Header */}
        <div className="p-3.5 sm:p-5 border-b border-[rgba(65,230,255,0.2)] bg-[rgba(10,24,36,0.8)] flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 sm:p-2.5 rounded-xl border ${
                isMorning
                  ? 'bg-[rgba(255,194,75,0.15)] border-[#ffc24b] text-[#ffc24b] shadow-[0_0_12px_rgba(255,194,75,0.3)]'
                  : 'bg-[rgba(186,104,255,0.15)] border-[#ba68ff] text-[#ba68ff] shadow-[0_0_12px_rgba(186,104,255,0.3)]'
              }`}
            >
              {isMorning ? <Sun size={20} /> : <Moon size={20} />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display text-sm sm:text-lg font-bold tracking-wider text-[#e8fbff]">
                  {isMorning ? 'MORNING INTELLIGENCE BRIEFING' : 'EVENING INTELLIGENCE DEBRIEF'}
                </h3>
                <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-[rgba(65,230,255,0.15)] text-[#41e6ff] border border-[rgba(65,230,255,0.3)]">
                  {briefing.time}
                </span>
              </div>
              <p className="font-mono text-[10.5px] text-[#7da4b8] mt-0.5">{briefing.date}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#41e6ff] transition-all"
              title="Copy Briefing Markdown"
            >
              {copied ? <Check size={14} className="text-[#4dff91]" /> : <Copy size={14} />}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#e8fbff] transition-all"
              title="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 p-3.5 sm:p-6 overflow-y-auto space-y-4 font-mono text-xs">
          {/* Spoken Summary Quote Card */}
          <div className="p-3.5 rounded-xl bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.25)] flex items-start gap-3">
            <Volume2 size={18} className="text-[#41e6ff] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-[#41e6ff] tracking-wider uppercase">
                A.T.H.E.N.A. Spoken Executive Summary
              </span>
              <p className="text-[#e8fbff] text-xs leading-relaxed opacity-95">{briefing.spoken_summary}</p>
            </div>
          </div>

          {/* Grid: Weather & Hardware Telemetry */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Weather Card */}
            <div className="p-3.5 rounded-xl bg-[rgba(10,24,36,0.6)] border border-[rgba(65,230,255,0.2)] space-y-2">
              <div className="flex items-center justify-between text-[#ffc24b]">
                <div className="flex items-center gap-1.5 font-bold tracking-wider text-[11px]">
                  <Cloud size={14} />
                  <span>ATMOSPHERIC CONDITIONS</span>
                </div>
                <span className="text-[10px] text-[#7da4b8]">{briefing.weather.city}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-display text-2xl sm:text-3xl font-bold text-[#e8fbff]">
                  {briefing.weather.temp_c}°C
                </span>
                <span className="text-[#7da4b8] text-xs">({briefing.weather.temp_f}°F)</span>
              </div>
              <div className="flex items-center justify-between text-[10.5px] text-[#7da4b8] border-t border-[rgba(65,230,255,0.1)] pt-2">
                <span>{briefing.weather.condition}</span>
                <span>💨 {briefing.weather.wind_kph} km/h wind</span>
              </div>
            </div>

            {/* Hardware Telemetry Card */}
            <div className="p-3.5 rounded-xl bg-[rgba(10,24,36,0.6)] border border-[rgba(65,230,255,0.2)] space-y-2">
              <div className="flex items-center justify-between text-[#41e6ff]">
                <div className="flex items-center gap-1.5 font-bold tracking-wider text-[11px]">
                  <Cpu size={14} />
                  <span>HOST HARDWARE TELEMETRY</span>
                </div>
                <span className="text-[10px] text-[#7da4b8]">{briefing.telemetry.hostname}</span>
              </div>

              <div className="space-y-1.5 text-[10.5px]">
                <div className="flex justify-between">
                  <span className="text-[#7da4b8]">CPU Load</span>
                  <span className="font-bold text-[#e8fbff]">{briefing.telemetry.cpu_percent}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-[rgba(65,230,255,0.1)] overflow-hidden">
                  <div
                    className="h-full bg-[#41e6ff] rounded-full transition-all"
                    style={{ width: `${Math.min(100, briefing.telemetry.cpu_percent)}%` }}
                  />
                </div>

                <div className="flex justify-between pt-1">
                  <span className="text-[#7da4b8]">Memory Used</span>
                  <span className="font-bold text-[#e8fbff]">
                    {briefing.telemetry.memory_used_gb} GB / {briefing.telemetry.memory_total_gb} GB (
                    {briefing.telemetry.memory_percent}%)
                  </span>
                </div>

                <div className="flex justify-between text-[#4dff91]">
                  <span className="text-[#7da4b8]">Power Status</span>
                  <span>⚡ {briefing.telemetry.battery}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Active To-Do Checklist */}
          <div className="p-3.5 rounded-xl bg-[rgba(10,24,36,0.6)] border border-[rgba(65,230,255,0.2)] space-y-2">
            <div className="flex items-center justify-between text-[#4dff91]">
              <div className="flex items-center gap-1.5 font-bold tracking-wider text-[11px]">
                <ListTodo size={14} />
                <span>ACTIVE TASKS & CHECKLIST</span>
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(77,255,145,0.15)] border border-[rgba(77,255,145,0.3)]">
                {briefing.todos.pending_count} PENDING
              </span>
            </div>

            {briefing.todos.pending.length === 0 ? (
              <div className="p-3 text-center text-[#7da4b8] text-[11px] italic flex items-center justify-center gap-1.5">
                <CheckCircle2 size={13} className="text-[#4dff91]" />
                <span>All tasks completed! Your agenda is clear.</span>
              </div>
            ) : (
              <div className="space-y-1.5 pl-1">
                {briefing.todos.pending.map((t, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-[11px] text-[#e8fbff]">
                    <span className="text-[#41e6ff]">◻</span>
                    <span className="flex-1 opacity-90">{t}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Top News Headlines */}
          {briefing.news && briefing.news.length > 0 && (
            <div className="p-3.5 rounded-xl bg-[rgba(10,24,36,0.6)] border border-[rgba(65,230,255,0.2)] space-y-2.5">
              <div className="flex items-center gap-1.5 text-[#ba68ff] font-bold tracking-wider text-[11px]">
                <Newspaper size={14} />
                <span>CURATED TECHNOLOGY HEADLINES</span>
              </div>

              <div className="space-y-2">
                {briefing.news.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded-lg bg-[rgba(6,14,21,0.6)] border border-[rgba(65,230,255,0.1)] space-y-0.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h5 className="font-bold text-[#e8fbff] text-[11px] leading-snug">{item.title}</h5>
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[#41e6ff] hover:text-[#ba68ff] shrink-0 mt-0.5"
                          title="Open article link"
                        >
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    {item.snippet && <p className="text-[10px] text-[#7da4b8] leading-relaxed">{item.snippet}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="p-3.5 sm:p-4 border-t border-[rgba(65,230,255,0.2)] bg-[rgba(10,24,36,0.8)] flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#e8fbff] font-mono text-xs transition-all"
          >
            DISMISS
          </button>

          <button
            onClick={handleReadAloud}
            className="px-4 py-1.5 rounded-lg bg-[rgba(65,230,255,0.2)] border border-[#41e6ff] text-[#41e6ff] hover:bg-[rgba(65,230,255,0.35)] shadow-[0_0_12px_rgba(65,230,255,0.3)] font-mono text-xs font-bold tracking-wider flex items-center gap-1.5 transition-all"
          >
            <Volume2 size={14} />
            <span>READ ALOUD WITH A.T.H.E.N.A.</span>
          </button>
        </div>
      </div>
    </div>
  )
}
