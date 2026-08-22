import { useState, useEffect, useCallback } from 'react'
import { BRIDGE_URL, type McpStatusResponse } from '../types'
import { soundFx } from '../lib/soundFx'

export function useMcp() {
  const [data, setData] = useState<McpStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMcp = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: McpStatusResponse = await res.json()
      setData(json)
      setError(null)
    } catch (err: any) {
      setError(err?.message || 'Failed to connect to MCP manager')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMcp()
    // Poll every 5s for live status updates if open
    const interval = setInterval(() => fetchMcp(true), 5000)
    return () => clearInterval(interval)
  }, [fetchMcp])

  const toggleServer = useCallback(async (name: string, enabled: boolean): Promise<boolean> => {
    soundFx.click()
    // Optimistic UI update
    setData((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        servers: prev.servers.map((s) =>
          s.name === name ? { ...s, enabled, running: enabled ? s.running : false } : s,
        ),
      }
    })

    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, enabled }),
      })
      const result = await res.json()
      if (result.ok) {
        if (enabled) {
          soundFx.responseReady()
        }
        await fetchMcp(true)
        return true
      } else {
        soundFx.error()
        await fetchMcp(true)
        return false
      }
    } catch {
      soundFx.error()
      await fetchMcp(true)
      return false
    }
  }, [fetchMcp])

  const restartServer = useCallback(async (name: string): Promise<boolean> => {
    soundFx.click()
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/restart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const result = await res.json()
      if (result.ok) {
        soundFx.responseReady()
        await fetchMcp(true)
        return true
      } else {
        soundFx.error()
        return false
      }
    } catch {
      soundFx.error()
      return false
    }
  }, [fetchMcp])

  const saveServer = useCallback(async (
    name: string,
    spec: { command: string; args: string[]; env?: Record<string, string>; enabled?: boolean },
  ): Promise<boolean> => {
    soundFx.uplink()
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, ...spec }),
      })
      const result = await res.json()
      if (result.ok) {
        soundFx.responseReady()
        await fetchMcp(true)
        return true
      } else {
        soundFx.error()
        return false
      }
    } catch {
      soundFx.error()
      return false
    }
  }, [fetchMcp])

  const updateServer = useCallback(async (
    name: string,
    updates: { command?: string; args?: string[]; env?: Record<string, string>; enabled?: boolean },
  ): Promise<boolean> => {
    soundFx.uplink()
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, ...updates }),
      })
      const result = await res.json()
      if (result.ok) {
        soundFx.responseReady()
        await fetchMcp(true)
        return true
      } else {
        soundFx.error()
        return false
      }
    } catch {
      soundFx.error()
      return false
    }
  }, [fetchMcp])

  const searchEcosystem = useCallback(async (query: string) => {
    if (!query.trim()) return null
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/search?q=${encodeURIComponent(query.trim())}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return await res.json()
    } catch {
      return null
    }
  }, [])

  const deleteServer = useCallback(async (name: string): Promise<boolean> => {
    soundFx.click()
    try {
      const res = await fetch(`${BRIDGE_URL}/mcp/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const result = await res.json()
      if (result.ok) {
        soundFx.responseReady()
        await fetchMcp(true)
        return true
      } else {
        soundFx.error()
        return false
      }
    } catch {
      soundFx.error()
      return false
    }
  }, [fetchMcp])

  return {
    data,
    loading,
    error,
    refresh: fetchMcp,
    toggleServer,
    restartServer,
    saveServer,
    updateServer,
    deleteServer,
    searchEcosystem,
  }
}

