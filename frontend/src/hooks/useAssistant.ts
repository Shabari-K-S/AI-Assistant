import { useCallback, useEffect, useRef, useState } from 'react'
import {
  BRIDGE_URL,
  DEFAULT_SNAPSHOT,
  type LogLine,
  type Snapshot,
} from '../types'
import { soundFx } from '../lib/soundFx'

let logSeq = 0

/**
 * Live connection to the assistant's bridge (SSE at :2027 via Vite proxy `/bridge`).
 * Streams snapshots + discrete events, and dispatches controls & terminal prompt commands.
 */
export function useAssistant() {
  const [snap, setSnap] = useState<Snapshot>(DEFAULT_SNAPSHOT)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const prevPhaseRef = useRef(snap.phase)

  useEffect(() => {
    const es = new EventSource(`${BRIDGE_URL}/stream`)

    const pushLog = (kind: LogLine['kind'], data: Record<string, unknown>) => {
      setLogs((prev) => {
        const line: LogLine = {
          id: `L${(logSeq += 1)}`,
          kind,
          level: data.level as string | undefined,
          msg: data.msg as string | undefined,
          text: data.text as string | undefined,
          confidence: data.confidence as number | undefined,
          t: Date.now(),
        }
        return [...prev.slice(-300), line]
      })
    }

    es.onopen = () => {
      setConnected(true)
    }

    es.onerror = () => {
      setConnected(false)
      setSnap((prev) => ({ ...prev, online: false, phase: 'standby' }))
    }

    es.addEventListener('snapshot', (e) => {
      try {
        const newSnap = JSON.parse((e as MessageEvent).data) as Snapshot
        setSnap(newSnap)

        // Trigger sound cues on phase changes
        if (prevPhaseRef.current !== newSnap.phase) {
          if (newSnap.phase === 'listening') {
            soundFx.wakeDetected()
          } else if (newSnap.phase === 'speaking') {
            soundFx.responseReady()
          }
          prevPhaseRef.current = newSnap.phase
        }
      } catch {
        /* malformed frame — ignore */
      }
    })

    es.addEventListener('log', (e) => {
      try {
        pushLog('log', JSON.parse((e as MessageEvent).data))
      } catch {
        /* ignore */
      }
    })

    es.addEventListener('transcript', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data)
        pushLog('transcript', data)
      } catch {
        /* ignore */
      }
    })

    es.addEventListener('reply', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data)
        pushLog('reply', data)
      } catch {
        /* ignore */
      }
    })

    es.addEventListener('error', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data)
        soundFx.error()
        pushLog('error', data)
      } catch {
        /* ignore */
      }
    })

    return () => {
      es.close()
    }
  }, [])

  const postConfig = useCallback(
    async (body: Record<string, unknown>) => {
      try {
        await fetch(`${BRIDGE_URL}/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } catch {
        /* offline — preview remains */
      }
    },
    [],
  )

  const sendPrompt = useCallback(
    async (text: string): Promise<boolean> => {
      const trimmed = text.trim()
      if (!trimmed) return false
      soundFx.uplink()
      setLogs((prev) => [
        ...prev,
        {
          id: `L${(logSeq += 1)}`,
          kind: 'command',
          text: trimmed,
          t: Date.now(),
        },
      ])
      try {
        const res = await fetch(`${BRIDGE_URL}/prompt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: trimmed }),
        })
        return res.ok
      } catch {
        soundFx.error()
        return false
      }
    },
    [],
  )

  const setThreshold = useCallback(
    (value: number) => postConfig({ threshold: value }),
    [postConfig],
  )

  const setMuted = useCallback(
    (muted: boolean) => postConfig({ muted }),
    [postConfig],
  )

  const clearLogs = useCallback(() => {
    setLogs([])
    soundFx.click()
  }, [])

  return {
    snap,
    logs,
    connected,
    setThreshold,
    setMuted,
    sendPrompt,
    clearLogs,
  }
}
