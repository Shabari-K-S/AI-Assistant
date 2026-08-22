import { useState, useEffect, useCallback, useMemo } from 'react'
import { BRIDGE_URL, type VaultNote, type VaultIndexResponse, type VaultNoteDetail } from '../types'
import { soundFx } from '../lib/soundFx'

export function useNotes() {
  const [notes, setNotes] = useState<VaultNote[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedNote, setSelectedNote] = useState<VaultNoteDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  const fetchNotes = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${BRIDGE_URL}/notes`)
      if (!res.ok) throw new Error(`HTTP error ${res.status}`)
      const data: VaultIndexResponse = await res.json()
      setNotes(data.notes || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load notes vault')
    } finally {
      setLoading(false)
    }
  }, [])

  const readNote = useCallback(async (target: string): Promise<VaultNoteDetail | null> => {
    setLoadingDetail(true)
    try {
      soundFx.click()
      const res = await fetch(`${BRIDGE_URL}/notes/read?target=${encodeURIComponent(target)}`)
      if (!res.ok) throw new Error(`Note not found (${res.status})`)
      const data: VaultNoteDetail = await res.json()
      setSelectedNote(data)
      return data
    } catch (err: any) {
      soundFx.error()
      setError(err.message || 'Failed to read note')
      return null
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const saveNote = useCallback(
    async (params: {
      title?: string
      content: string
      category?: string
      tags?: string[]
      target?: string
      append?: boolean
    }) => {
      try {
        soundFx.uplink()
        const res = await fetch(`${BRIDGE_URL}/notes/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        })
        const data = await res.json()
        if (data.ok) {
          soundFx.responseReady()
          await fetchNotes()
          if (params.target || params.title) {
            await readNote(params.target || params.title || '')
          }
          return { ok: true, result: data.result }
        } else {
          soundFx.error()
          return { ok: false, error: data.error || 'Save failed' }
        }
      } catch (err: any) {
        soundFx.error()
        return { ok: false, error: err.message || 'Save failed' }
      }
    },
    [fetchNotes, readNote],
  )

  const deleteNote = useCallback(
    async (target: string) => {
      try {
        soundFx.click()
        const res = await fetch(`${BRIDGE_URL}/notes/delete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target }),
        })
        const data = await res.json()
        if (data.ok) {
          soundFx.responseReady()
          if (selectedNote?.id === target || selectedNote?.title === target || selectedNote?.path.includes(target)) {
            setSelectedNote(null)
          }
          await fetchNotes()
          return { ok: true, result: data.result }
        } else {
          soundFx.error()
          return { ok: false, error: data.error || 'Delete failed' }
        }
      } catch (err: any) {
        soundFx.error()
        return { ok: false, error: err.message || 'Delete failed' }
      }
    },
    [fetchNotes, selectedNote],
  )

  useEffect(() => {
    fetchNotes()

    let es: EventSource | null = null
    try {
      es = new EventSource(`${BRIDGE_URL}/stream`)
      es.addEventListener('notes_changed', () => {
        fetchNotes()
      })
    } catch {
      /* ignore */
    }

    const handleFocus = () => {
      fetchNotes()
    }
    window.addEventListener('focus', handleFocus)

    return () => {
      if (es) es.close()
      window.removeEventListener('focus', handleFocus)
    }
  }, [fetchNotes])

  const categories = useMemo(() => {
    const set = new Set<string>()
    const preferredOrder = ['all', 'lab-dossiers', 'ctf', 'security-reports', 'deep-research', 'general', 'work', 'ideas', 'todos']
    
    notes.forEach((n) => {
      if (n.category) set.add(n.category.toLowerCase())
    })

    const presentCategories = Array.from(set)
    const sorted = [
      ...preferredOrder.filter((c) => c === 'all' || presentCategories.includes(c)),
      ...presentCategories.filter((c) => !preferredOrder.includes(c)).sort(),
    ]
    return sorted
  }, [notes])

  const filteredNotes = useMemo(() => {
    const q = searchQuery.toLowerCase().trim()
    return notes.filter((n) => {
      const matchCat =
        selectedCategory === 'all' || n.category?.toLowerCase() === selectedCategory.toLowerCase()
      if (!matchCat) return false

      if (!q) return true
      const matchTitle = n.title?.toLowerCase().includes(q)
      const matchPreview = n.preview?.toLowerCase().includes(q)
      const matchTags = n.tags?.some((t) => t.toLowerCase().includes(q))
      const matchCatName = n.category?.toLowerCase().includes(q)
      return matchTitle || matchPreview || matchTags || matchCatName
    })
  }, [notes, selectedCategory, searchQuery])

  return {
    notes: filteredNotes,
    allNotesCount: notes.length,
    loading,
    error,
    selectedNote,
    setSelectedNote,
    loadingDetail,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    categories,
    fetchNotes,
    readNote,
    saveNote,
    deleteNote,
  }
}
