import { useState } from 'react'
import { Timer, Clock, Coffee, Play, X, Plus } from 'lucide-react'
import type { ActiveTimer } from '../types'
import { soundFx } from '../lib/soundFx'

interface Props {
  timers: ActiveTimer[]
  onCreateTimer: (duration: string, label?: string, type?: 'timer' | 'pomodoro' | 'break') => Promise<any>
  onCancelTimer: (id: string) => Promise<any>
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function ActiveTimersBar({ timers, onCreateTimer, onCancelTimer }: Props) {
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [customDuration, setCustomDuration] = useState('')
  const [customLabel, setCustomLabel] = useState('')

  const handleCreateCustom = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customDuration.trim()) return
    await onCreateTimer(customDuration.trim(), customLabel.trim())
    setCustomDuration('')
    setCustomLabel('')
    setShowAddMenu(false)
  }

  return (
    <div className="w-full bg-[rgba(6,14,21,0.85)] border-b border-[rgba(65,230,255,0.18)] px-3 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs font-mono backdrop-blur-md">
      {/* Left: Active Timers Chips */}
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-none py-0.5 max-w-full">
        <div className="flex items-center gap-1 text-[#41e6ff] font-bold tracking-wider text-[11px] shrink-0">
          <Clock size={13} className="animate-pulse" />
          <span className="hidden sm:inline">TIMERS</span>
        </div>

        {timers.length === 0 ? (
          <span className="text-[#7da4b8]/60 text-[10.5px] italic pl-1">No active timers</span>
        ) : (
          timers.map((t) => {
            const isPomodoro = t.timer_type === 'pomodoro'
            const isBreak = t.timer_type === 'break'
            const isReminder = t.timer_type === 'reminder' || t.is_reminder

            const colorClass = isPomodoro
              ? 'border-[#ba68ff] bg-[rgba(186,104,255,0.15)] text-[#ba68ff] shadow-[0_0_8px_rgba(186,104,255,0.3)]'
              : isBreak
                ? 'border-[#4dff91] bg-[rgba(77,255,145,0.15)] text-[#4dff91]'
                : isReminder
                  ? 'border-[#ffc24b] bg-[rgba(255,194,75,0.15)] text-[#ffc24b]'
                  : 'border-[#41e6ff] bg-[rgba(65,230,255,0.15)] text-[#41e6ff]'

            return (
              <div
                key={t.id}
                className={`flex items-center gap-2 px-2.5 py-0.5 rounded-full border ${colorClass} transition-all shrink-0`}
              >
                {isPomodoro && <Timer size={11} />}
                {isBreak && <Coffee size={11} />}
                {isReminder && <Clock size={11} />}

                <span className="font-bold text-[11px] tracking-wider">{formatTime(t.remaining_seconds)}</span>
                <span className="text-[9.5px] max-w-[110px] truncate opacity-80">{t.label}</span>

                <button
                  onClick={() => onCancelTimer(t.id)}
                  className="p-0.5 hover:text-white transition-colors"
                  title="Cancel Timer"
                >
                  <X size={11} />
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* Right: Quick Action Presets & Add Form */}
      <div className="flex items-center gap-1.5 shrink-0 ml-auto">
        <button
          onClick={() => onCreateTimer('25m', 'Pomodoro Focus', 'pomodoro')}
          className="px-2 py-0.5 rounded bg-[rgba(186,104,255,0.12)] border border-[rgba(186,104,255,0.3)] text-[#ba68ff] hover:bg-[rgba(186,104,255,0.25)] text-[10px] flex items-center gap-1 transition-all"
          title="Start 25m Pomodoro Focus"
        >
          <Timer size={10} />
          <span>25m FOCUS</span>
        </button>

        <button
          onClick={() => onCreateTimer('5m', 'Short Break', 'break')}
          className="px-2 py-0.5 rounded bg-[rgba(77,255,145,0.1)] border border-[rgba(77,255,145,0.3)] text-[#4dff91] hover:bg-[rgba(77,255,145,0.2)] text-[10px] flex items-center gap-1 transition-all"
          title="Start 5m Break"
        >
          <Coffee size={10} />
          <span>5m BREAK</span>
        </button>

        <button
          onClick={() => {
            soundFx.click()
            setShowAddMenu(!showAddMenu)
          }}
          className={`p-1 rounded border transition-all ${
            showAddMenu
              ? 'bg-[#41e6ff] text-black border-[#41e6ff]'
              : 'bg-[rgba(65,230,255,0.1)] border-[rgba(65,230,255,0.3)] text-[#41e6ff] hover:bg-[rgba(65,230,255,0.2)]'
          }`}
          title="Custom Timer"
        >
          <Plus size={12} />
        </button>
      </div>

      {/* Popover Custom Timer Form */}
      {showAddMenu && (
        <form
          onSubmit={handleCreateCustom}
          className="w-full mt-1.5 p-2 rounded-lg bg-[rgba(10,24,36,0.95)] border border-[rgba(65,230,255,0.3)] flex flex-wrap items-center gap-2 shadow-[0_4px_16px_rgba(0,0,0,0.6)] animate-in fade-in"
        >
          <input
            type="text"
            placeholder="Duration (e.g. 15m, 45s, 1h)"
            value={customDuration}
            onChange={(e) => setCustomDuration(e.target.value)}
            className="px-2.5 py-1 rounded bg-[rgba(6,14,21,0.9)] border border-[rgba(65,230,255,0.25)] text-xs text-[#e8fbff] focus:outline-none focus:border-[#41e6ff] w-36"
            autoFocus
          />
          <input
            type="text"
            placeholder="Label (optional)"
            value={customLabel}
            onChange={(e) => setCustomLabel(e.target.value)}
            className="flex-1 min-w-[140px] px-2.5 py-1 rounded bg-[rgba(6,14,21,0.9)] border border-[rgba(65,230,255,0.25)] text-xs text-[#e8fbff] focus:outline-none focus:border-[#41e6ff]"
          />
          <button
            type="submit"
            className="px-3 py-1 rounded bg-[rgba(65,230,255,0.2)] border border-[#41e6ff] text-[#41e6ff] hover:bg-[rgba(65,230,255,0.35)] text-xs font-bold flex items-center gap-1"
          >
            <Play size={11} />
            <span>START</span>
          </button>
          <button
            type="button"
            onClick={() => setShowAddMenu(false)}
            className="px-2 py-1 rounded bg-[rgba(65,230,255,0.05)] text-[#7da4b8] hover:text-[#e8fbff] text-xs"
          >
            Cancel
          </button>
        </form>
      )}
    </div>
  )
}
