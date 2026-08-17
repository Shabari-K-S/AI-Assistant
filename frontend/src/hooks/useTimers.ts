import { useState, useEffect, useCallback } from 'react'
import type { ActiveTimer, DailyBriefing } from '../types'
import { soundFx } from '../lib/soundFx'

const API_BASE = 'http://localhost:2027'

export function useTimers() {
  const [timers, setTimers] = useState<ActiveTimer[]>([])
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null)
  const [loadingBriefing, setLoadingBriefing] = useState(false)

  const fetchTimers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/timers`)
      if (res.ok) {
        const data = await res.json()
        if (data.ok && Array.isArray(data.timers)) {
          setTimers(data.timers)
        }
      }
    } catch {
      // Offline or connecting
    }
  }, [])

  useEffect(() => {
    fetchTimers()
    const interval = setInterval(fetchTimers, 1000)
    return () => clearInterval(interval)
  }, [fetchTimers])

  const createTimer = useCallback(
    async (duration: string, label = '', type: 'timer' | 'pomodoro' | 'break' = 'timer') => {
      try {
        soundFx.click()
        const res = await fetch(`${API_BASE}/timers/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ duration, label, type }),
        })
        const data = await res.json()
        if (data.ok) {
          fetchTimers()
        }
        return data
      } catch (err) {
        return { ok: false, error: String(err) }
      }
    },
    [fetchTimers],
  )

  const cancelTimer = useCallback(
    async (id: string) => {
      try {
        soundFx.click()
        const res = await fetch(`${API_BASE}/timers/cancel`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id }),
        })
        const data = await res.json()
        if (data.ok) {
          fetchTimers()
        }
        return data
      } catch (err) {
        return { ok: false, error: String(err) }
      }
    },
    [fetchTimers],
  )

  const fetchBriefing = useCallback(async (type: 'morning' | 'evening' = 'morning') => {
    setLoadingBriefing(true)
    try {
      soundFx.uplink()
      const res = await fetch(`${API_BASE}/briefing?type=${type}`)
      if (res.ok) {
        const data: DailyBriefing = await res.json()
        setBriefing(data)
        return data
      }
    } catch (err) {
      console.error('Failed to fetch daily briefing:', err)
    } finally {
      setLoadingBriefing(false)
    }
    return null
  }, [])

  return {
    timers,
    createTimer,
    cancelTimer,
    fetchTimers,
    briefing,
    setBriefing,
    loadingBriefing,
    fetchBriefing,
  }
}
