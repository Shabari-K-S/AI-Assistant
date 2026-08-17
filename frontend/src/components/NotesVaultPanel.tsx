import { useState, useMemo, useCallback, type ReactNode } from 'react'
import {
  BookOpen,
  Search,
  Sparkles,
  Plus,
  RefreshCw,
  Edit3,
  Trash2,
  Copy,
  Check,
  FileText,
  Calendar,
  X,
  ExternalLink,
} from 'lucide-react'
import { useNotes } from '../hooks/useNotes'
import { soundFx } from '../lib/soundFx'
import type { VaultNoteDetail } from '../types'

interface Props {
  onSendPrompt: (prompt: string) => Promise<boolean> | Promise<void> | void
}

// Category color mapping
const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  'deep-research': {
    bg: 'bg-[rgba(186,104,255,0.15)]',
    text: 'text-[#ba68ff]',
    border: 'border-[rgba(186,104,255,0.4)]',
    glow: 'shadow-[0_0_8px_rgba(186,104,255,0.3)]',
  },
  general: {
    bg: 'bg-[rgba(65,230,255,0.12)]',
    text: 'text-[#41e6ff]',
    border: 'border-[rgba(65,230,255,0.3)]',
    glow: 'shadow-[0_0_8px_rgba(65,230,255,0.2)]',
  },
  work: {
    bg: 'bg-[rgba(255,194,75,0.15)]',
    text: 'text-[#ffc24b]',
    border: 'border-[rgba(255,194,75,0.4)]',
    glow: 'shadow-[0_0_8px_rgba(255,194,75,0.25)]',
  },
  ideas: {
    bg: 'bg-[rgba(77,255,145,0.15)]',
    text: 'text-[#4dff91]',
    border: 'border-[rgba(77,255,145,0.4)]',
    glow: 'shadow-[0_0_8px_rgba(77,255,145,0.25)]',
  },
  todos: {
    bg: 'bg-[rgba(255,93,93,0.15)]',
    text: 'text-[#ff5d5d]',
    border: 'border-[rgba(255,93,93,0.4)]',
    glow: 'shadow-[0_0_8px_rgba(255,93,93,0.25)]',
  },
}

function getCategoryStyle(cat?: string) {
  const c = cat?.toLowerCase() || 'general'
  return (
    CATEGORY_COLORS[c] || {
      bg: 'bg-[rgba(65,230,255,0.1)]',
      text: 'text-[#41e6ff]',
      border: 'border-[rgba(65,230,255,0.25)]',
      glow: '',
    }
  )
}

/**
 * Lightweight Markdown text renderer formatted for Cyberpunk HUD
 */
function MarkdownRenderer({ content }: { content: string }) {
  const lines = useMemo(() => content.split('\n'), [content])

  return (
    <div className="space-y-3 font-sans text-[#e8fbff] text-sm leading-relaxed select-text">
      {lines.map((line, idx) => {
        const trimmed = line.trim()

        if (!trimmed) {
          return <div key={idx} className="h-2" />
        }

        // Header 1
        if (trimmed.startsWith('# ')) {
          return (
            <h1
              key={idx}
              className="font-display text-xl sm:text-2xl font-bold tracking-wider text-[#41e6ff] border-b border-[rgba(65,230,255,0.3)] pb-1.5 mt-4 mb-2 flex items-center gap-2 drop-shadow-[0_0_8px_rgba(65,230,255,0.4)]"
            >
              <span>{trimmed.slice(2)}</span>
            </h1>
          )
        }

        // Header 2
        if (trimmed.startsWith('## ')) {
          return (
            <h2
              key={idx}
              className="font-display text-base sm:text-lg font-bold tracking-wide text-[#ba68ff] mt-4 mb-1.5 flex items-center gap-2"
            >
              <span>{trimmed.slice(3)}</span>
            </h2>
          )
        }

        // Header 3
        if (trimmed.startsWith('### ')) {
          return (
            <h3
              key={idx}
              className="font-display text-sm sm:text-base font-semibold text-[#ffc24b] mt-3 mb-1"
            >
              {trimmed.slice(4)}
            </h3>
          )
        }

        // Bullet point
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const text = trimmed.slice(2)
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-[#41e6ff] font-mono text-xs mt-1">▸</span>
              <span className="flex-1 opacity-90">{renderFormattedText(text)}</span>
            </div>
          )
        }

        // Checkbox todo item
        if (trimmed.startsWith('- [ ] ') || trimmed.startsWith('- [x] ') || trimmed.startsWith('- [X] ')) {
          const isDone = trimmed.startsWith('- [x] ') || trimmed.startsWith('- [X] ')
          const text = trimmed.slice(6)
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-2 py-0.5">
              <span
                className={`font-mono text-xs px-1 rounded ${
                  isDone
                    ? 'bg-[rgba(77,255,145,0.2)] text-[#4dff91] border border-[rgba(77,255,145,0.4)]'
                    : 'bg-[rgba(65,230,255,0.1)] text-[#41e6ff] border border-[rgba(65,230,255,0.3)]'
                }`}
              >
                {isDone ? '✓ DONE' : '◻ PEND'}
              </span>
              <span className={`flex-1 ${isDone ? 'line-through opacity-50' : 'opacity-90'}`}>
                {renderFormattedText(text)}
              </span>
            </div>
          )
        }

        // Numbered list
        if (/^\d+\.\s/.test(trimmed)) {
          const match = trimmed.match(/^(\d+)\.\s(.*)$/)
          if (match) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="font-mono text-xs text-[#ffc24b] font-bold mt-0.5">
                  {match[1]}.
                </span>
                <span className="flex-1 opacity-90">{renderFormattedText(match[2])}</span>
              </div>
            )
          }
        }

        // Blockquote
        if (trimmed.startsWith('> ')) {
          return (
            <div
              key={idx}
              className="border-l-2 border-[#ba68ff] bg-[rgba(186,104,255,0.06)] pl-3 py-1 my-1 text-xs italic text-[#e8fbff] opacity-85 rounded-r"
            >
              {renderFormattedText(trimmed.slice(2))}
            </div>
          )
        }

        // Code block or horizontal rule
        if (trimmed.startsWith('```')) {
          return (
            <div key={idx} className="font-mono text-xs text-[#7da4b8] opacity-60">
              {trimmed}
            </div>
          )
        }
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={idx} className="border-[rgba(65,230,255,0.2)] my-3" />
        }

        // Regular paragraph text
        return (
          <p key={idx} className="opacity-90 leading-relaxed">
            {renderFormattedText(trimmed)}
          </p>
        )
      })}
    </div>
  )
}

function renderFormattedText(text: string) {
  // Simple regex parser for **bold**, `code`, [link](url)
  const parts: (string | ReactNode)[] = []
  let keyIndex = 0

  // Regex to split by bold, inline code, and links
  const tokenRegex = /(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }

    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={keyIndex++} className="font-bold text-[#ffffff] drop-shadow-[0_0_4px_rgba(65,230,255,0.4)]">
          {token.slice(2, -2)}
        </strong>,
      )
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={keyIndex++}
          className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-[rgba(65,230,255,0.1)] text-[#41e6ff] border border-[rgba(65,230,255,0.25)] mx-0.5"
        >
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('[') && token.includes('](')) {
      const linkMatch = token.match(/\[(.*?)\]\((.*?)\)/)
      if (linkMatch) {
        parts.push(
          <a
            key={keyIndex++}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-[#41e6ff] underline underline-offset-2 hover:text-[#ba68ff] transition-colors"
          >
            <span>{linkMatch[1]}</span>
            <ExternalLink size={10} className="inline opacity-70" />
          </a>,
        )
      }
    }

    lastIndex = tokenRegex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return <>{parts}</>
}

export function NotesVaultPanel({ onSendPrompt }: Props) {
  const {
    notes,
    allNotesCount,
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
  } = useNotes()

  const [isEditing, setIsEditing] = useState(false)
  const [copied, setCopied] = useState(false)
  const [askStatus, setAskStatus] = useState(false)

  // Editor form state
  const [formTitle, setFormTitle] = useState('')
  const [formCategory, setFormCategory] = useState('general')
  const [formContent, setFormContent] = useState('')
  const [formTags, setFormTags] = useState('')
  const [saving, setSaving] = useState(false)

  const startNewNote = useCallback(() => {
    soundFx.click()
    setSelectedNote(null)
    setFormTitle('')
    setFormCategory('general')
    setFormContent('# New Note\n\nWrite your thoughts, ideas, or markdown notes here...')
    setFormTags('')
    setIsEditing(true)
  }, [setSelectedNote])

  const startEditNote = useCallback(
    (note: VaultNoteDetail) => {
      soundFx.click()
      setFormTitle(note.title)
      setFormCategory(note.category || 'general')
      setFormContent(note.content)
      setFormTags(note.tags?.join(', ') || '')
      setIsEditing(true)
    },
    [],
  )

  const handleSave = useCallback(async () => {
    if (!formTitle.trim() && !formContent.trim()) return
    setSaving(true)
    const tagsArr = formTags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    const res = await saveNote({
      target: selectedNote ? selectedNote.path || selectedNote.id : undefined,
      title: formTitle.trim(),
      content: formContent.trim(),
      category: formCategory.trim(),
      tags: tagsArr,
    })

    setSaving(false)
    if (res.ok) {
      setIsEditing(false)
    }
  }, [formTitle, formContent, formCategory, formTags, selectedNote, saveNote])

  const handleCopyMarkdown = useCallback(() => {
    if (!selectedNote) return
    soundFx.click()
    navigator.clipboard.writeText(selectedNote.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [selectedNote])

  const handleAskSara = useCallback(async () => {
    if (!selectedNote) return
    soundFx.uplink()
    setAskStatus(true)
    const prompt = `Sara, please provide a concise executive summary and key insights regarding my note: "${selectedNote.title}".`
    await onSendPrompt(prompt)
    setTimeout(() => setAskStatus(false), 2500)
  }, [selectedNote, onSendPrompt])

  const handleDelete = useCallback(async () => {
    if (!selectedNote) return
    const confirm = window.confirm(`Are you sure you want to delete note "${selectedNote.title}" from the vault?`)
    if (!confirm) return
    await deleteNote(selectedNote.path || selectedNote.id)
    setIsEditing(false)
  }, [selectedNote, deleteNote])

  return (
    <div className="flex flex-col h-full bg-[#060e15]/95 border border-[rgba(65,230,255,0.2)] rounded-xl overflow-hidden shadow-[0_0_30px_rgba(6,14,21,0.8)] backdrop-blur-md">
      {/* Vault Top Control Deck */}
      <div className="p-3 sm:p-4 border-b border-[rgba(65,230,255,0.2)] bg-[rgba(10,24,36,0.75)] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[rgba(65,230,255,0.1)] border border-[rgba(65,230,255,0.3)] text-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.25)]">
            <BookOpen size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-sm sm:text-base font-bold tracking-[0.2em] text-[#e8fbff]">
                NOTES & RESEARCH VAULT
              </h2>
              <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-[rgba(65,230,255,0.15)] text-[#41e6ff] border border-[rgba(65,230,255,0.3)]">
                .MD REPO
              </span>
            </div>
            <p className="font-mono text-[10px] sm:text-[11px] text-[#7da4b8] mt-0.5">
              {allNotesCount} saved documents • {categories.length - 1} categories • Persistent memory
            </p>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={fetchNotes}
            disabled={loading}
            className="px-2.5 py-1.5 rounded-lg bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#41e6ff] hover:border-[#41e6ff] transition-all flex items-center gap-1.5 font-mono text-xs"
            title="Refresh Notes Index"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin text-[#41e6ff]' : ''} />
            <span className="hidden sm:inline">REFRESH</span>
          </button>
          <button
            onClick={startNewNote}
            className="px-3 py-1.5 rounded-lg bg-[rgba(65,230,255,0.18)] border border-[#41e6ff] text-[#41e6ff] hover:bg-[rgba(65,230,255,0.3)] hover:shadow-[0_0_12px_rgba(65,230,255,0.4)] transition-all flex items-center gap-1.5 font-mono text-xs font-bold tracking-wider"
          >
            <Plus size={14} />
            <span>NEW NOTE</span>
          </button>
        </div>
      </div>

      {/* Category Pills & Live Search Filter */}
      <div className="px-3 sm:px-4 py-2.5 border-b border-[rgba(65,230,255,0.15)] bg-[rgba(8,18,28,0.6)] flex flex-wrap items-center justify-between gap-2.5">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 max-w-full scrollbar-none">
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat
            const isDeepResearch = cat === 'deep-research'

            return (
              <button
                key={cat}
                onClick={() => {
                  soundFx.click()
                  setSelectedCategory(cat)
                }}
                className={`px-2.5 py-1 rounded-md font-mono text-[11px] tracking-wider transition-all whitespace-nowrap flex items-center gap-1.5 ${
                  isSelected
                    ? isDeepResearch
                      ? 'bg-[rgba(186,104,255,0.25)] border border-[#ba68ff] text-[#ba68ff] shadow-[0_0_10px_rgba(186,104,255,0.4)] font-bold'
                      : 'bg-[rgba(65,230,255,0.2)] border border-[#41e6ff] text-[#41e6ff] shadow-[0_0_10px_rgba(65,230,255,0.3)] font-bold'
                    : 'bg-[rgba(65,230,255,0.05)] border border-[rgba(65,230,255,0.15)] text-[#7da4b8] hover:text-[#e8fbff]'
                }`}
              >
                {isDeepResearch && <Sparkles size={11} className="text-[#ba68ff]" />}
                <span>{cat.toUpperCase()}</span>
              </button>
            )
          })}
        </div>

        {/* Live Search Input */}
        <div className="relative flex-1 sm:flex-initial sm:w-64">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#7da4b8]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search notes, tags, contents..."
            className="w-full pl-8 pr-7 py-1 rounded-md bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] text-xs text-[#e8fbff] placeholder-[#7da4b8]/50 focus:outline-none focus:border-[#41e6ff] focus:shadow-[0_0_8px_rgba(65,230,255,0.3)] font-mono"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[#7da4b8] hover:text-[#e8fbff]"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Main Split Layout: Left List + Right Reader/Editor */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 min-h-0 overflow-hidden">
        {/* Left Master List */}
        <div className="md:col-span-4 lg:col-span-4 border-r border-[rgba(65,230,255,0.15)] overflow-y-auto p-2.5 sm:p-3 space-y-2 bg-[rgba(6,14,21,0.4)]">
          {error && (
            <div className="p-3 rounded-lg bg-[rgba(255,93,93,0.1)] border border-[rgba(255,93,93,0.3)] text-[#ff5d5d] text-xs font-mono">
              ⚠️ {error}
            </div>
          )}

          {notes.length === 0 && !loading && (
            <div className="p-6 text-center text-[#7da4b8] font-mono text-xs flex flex-col items-center gap-2">
              <FileText size={28} className="opacity-40" />
              <span>No notes found matching current filter</span>
              <button
                onClick={startNewNote}
                className="mt-2 text-[#41e6ff] underline underline-offset-2 hover:text-[#ba68ff]"
              >
                Create your first note
              </button>
            </div>
          )}

          {notes.map((note) => {
            const isSelected = selectedNote?.id === note.id || selectedNote?.path === note.path
            const style = getCategoryStyle(note.category)
            const isDeep = note.category?.toLowerCase() === 'deep-research'

            return (
              <div
                key={note.id || note.path}
                onClick={() => {
                  setIsEditing(false)
                  readNote(note.path || note.id)
                }}
                className={`p-2.5 rounded-lg border transition-all cursor-pointer group ${
                  isSelected
                    ? `${style.bg} ${style.border} ${style.glow}`
                    : 'bg-[rgba(10,24,36,0.4)] border-[rgba(65,230,255,0.12)] hover:border-[rgba(65,230,255,0.3)] hover:bg-[rgba(10,24,36,0.7)]'
                }`}
              >
                {/* Note Header Badges */}
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span
                    className={`font-mono text-[9px] px-1.5 py-0.5 rounded border uppercase tracking-wider ${style.bg} ${style.text} ${style.border}`}
                  >
                    {isDeep ? '🔬 ' : ''}
                    {note.category || 'general'}
                  </span>
                  <span className="font-mono text-[9px] text-[#7da4b8]">{note.created_at?.split(' ')[0] || ''}</span>
                </div>

                {/* Title */}
                <h4
                  className={`font-display text-xs sm:text-sm font-semibold tracking-wide truncate group-hover:text-[#41e6ff] transition-colors ${
                    isSelected ? style.text : 'text-[#e8fbff]'
                  }`}
                >
                  {note.title}
                </h4>

                {/* Preview Snippet */}
                <p className="font-mono text-[10px] text-[#7da4b8] opacity-75 line-clamp-2 mt-1 leading-snug">
                  {note.preview}
                </p>

                {/* Tags */}
                {note.tags && note.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {note.tags.slice(0, 3).map((tag, tIdx) => (
                      <span
                        key={tIdx}
                        className="font-mono text-[8.5px] px-1 rounded bg-[rgba(65,230,255,0.06)] text-[#7da4b8] border border-[rgba(65,230,255,0.15)]"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Right Detail Reader & Editor */}
        <div className="md:col-span-8 lg:col-span-8 flex flex-col h-full min-h-0 bg-[rgba(6,14,21,0.6)] overflow-hidden">
          {/* Case 1: Editor Mode */}
          {isEditing ? (
            <div className="flex-1 flex flex-col p-4 overflow-y-auto space-y-3">
              <div className="flex items-center justify-between border-b border-[rgba(65,230,255,0.2)] pb-2">
                <div className="flex items-center gap-2">
                  <Edit3 size={16} className="text-[#41e6ff]" />
                  <h3 className="font-display text-sm font-bold tracking-wider text-[#41e6ff]">
                    {selectedNote ? 'EDIT MARKDOWN NOTE' : 'NEW MARKDOWN NOTE'}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsEditing(false)}
                    className="px-2.5 py-1 rounded bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] text-xs font-mono hover:text-[#e8fbff]"
                  >
                    CANCEL
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="px-3 py-1 rounded bg-[rgba(65,230,255,0.2)] border border-[#41e6ff] text-[#41e6ff] text-xs font-mono font-bold hover:bg-[rgba(65,230,255,0.35)] shadow-[0_0_8px_rgba(65,230,255,0.3)] flex items-center gap-1.5"
                  >
                    <Check size={13} />
                    <span>{saving ? 'SAVING...' : 'SAVE NOTE'}</span>
                  </button>
                </div>
              </div>

              {/* Title & Category Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <div className="sm:col-span-2">
                  <label className="block font-mono text-[10px] text-[#7da4b8] mb-1">NOTE TITLE</label>
                  <input
                    type="text"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    placeholder="Enter note title..."
                    className="w-full px-3 py-1.5 rounded-lg bg-[rgba(10,24,36,0.8)] border border-[rgba(65,230,255,0.25)] text-xs text-[#e8fbff] focus:outline-none focus:border-[#41e6ff] font-mono"
                  />
                </div>
                <div>
                  <label className="block font-mono text-[10px] text-[#7da4b8] mb-1">CATEGORY</label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-[rgba(10,24,36,0.8)] border border-[rgba(65,230,255,0.25)] text-xs text-[#e8fbff] focus:outline-none focus:border-[#41e6ff] font-mono"
                  >
                    <option value="general">GENERAL</option>
                    <option value="deep-research">DEEP-RESEARCH</option>
                    <option value="work">WORK</option>
                    <option value="ideas">IDEAS</option>
                    <option value="todos">TODOS</option>
                  </select>
                </div>
              </div>

              {/* Tags Input */}
              <div>
                <label className="block font-mono text-[10px] text-[#7da4b8] mb-1">TAGS (COMMA SEPARATED)</label>
                <input
                  type="text"
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  placeholder="e.g. quantum, batteries, research"
                  className="w-full px-3 py-1.5 rounded-lg bg-[rgba(10,24,36,0.8)] border border-[rgba(65,230,255,0.25)] text-xs text-[#e8fbff] focus:outline-none focus:border-[#41e6ff] font-mono"
                />
              </div>

              {/* Markdown Content Textarea */}
              <div className="flex-1 flex flex-col min-h-[220px]">
                <label className="block font-mono text-[10px] text-[#7da4b8] mb-1">MARKDOWN BODY CONTENT</label>
                <textarea
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  placeholder="Write formatted markdown..."
                  className="w-full flex-1 p-3 rounded-lg bg-[rgba(6,14,21,0.9)] border border-[rgba(65,230,255,0.25)] text-xs font-mono text-[#e8fbff] focus:outline-none focus:border-[#41e6ff] leading-relaxed resize-none"
                />
              </div>
            </div>
          ) : selectedNote ? (
            /* Case 2: Reader View */
            <div className="flex-1 flex flex-col h-full min-h-0">
              {/* Reader Header Toolbar */}
              <div className="p-3 sm:p-4 border-b border-[rgba(65,230,255,0.2)] bg-[rgba(10,24,36,0.7)] flex flex-wrap items-center justify-between gap-2.5">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-mono text-[9px] px-2 py-0.5 rounded border uppercase tracking-wider ${
                        getCategoryStyle(selectedNote.category).bg
                      } ${getCategoryStyle(selectedNote.category).text} ${
                        getCategoryStyle(selectedNote.category).border
                      }`}
                    >
                      {selectedNote.category?.toLowerCase() === 'deep-research' ? '🔬 ' : ''}
                      {selectedNote.category?.toUpperCase() || 'GENERAL'}
                    </span>
                    <span className="font-mono text-[10px] text-[#7da4b8] flex items-center gap-1">
                      <Calendar size={11} />
                      {selectedNote.created_at}
                    </span>
                  </div>
                  <h3 className="font-display text-base sm:text-lg font-bold tracking-wide text-[#e8fbff] mt-1">
                    {selectedNote.title}
                  </h3>
                  <div className="font-mono text-[9px] text-[#7da4b8] opacity-60 mt-0.5">
                    File: {selectedNote.path}
                  </div>
                </div>

                {/* Toolbar Buttons */}
                <div className="flex items-center flex-wrap gap-1.5">
                  <button
                    onClick={handleAskSara}
                    disabled={askStatus}
                    className="px-2.5 py-1 rounded bg-[rgba(186,104,255,0.18)] border border-[rgba(186,104,255,0.4)] text-[#ba68ff] hover:bg-[rgba(186,104,255,0.3)] transition-all font-mono text-[11px] font-bold flex items-center gap-1 shadow-[0_0_8px_rgba(186,104,255,0.25)]"
                    title="Ask S.A.R.A. to summarize or give insights on this note"
                  >
                    <Sparkles size={12} />
                    <span>{askStatus ? 'TRANSMITTING...' : 'ASK S.A.R.A.'}</span>
                  </button>
                  <button
                    onClick={handleCopyMarkdown}
                    className="p-1.5 rounded bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#41e6ff] hover:border-[#41e6ff] transition-all"
                    title="Copy Markdown"
                  >
                    {copied ? <Check size={14} className="text-[#4dff91]" /> : <Copy size={14} />}
                  </button>
                  <button
                    onClick={() => startEditNote(selectedNote)}
                    className="p-1.5 rounded bg-[rgba(65,230,255,0.08)] border border-[rgba(65,230,255,0.2)] text-[#7da4b8] hover:text-[#41e6ff] hover:border-[#41e6ff] transition-all"
                    title="Edit Markdown Note"
                  >
                    <Edit3 size={14} />
                  </button>
                  <button
                    onClick={handleDelete}
                    className="p-1.5 rounded bg-[rgba(255,93,93,0.08)] border border-[rgba(255,93,93,0.2)] text-[#7da4b8] hover:text-[#ff5d5d] hover:border-[#ff5d5d] transition-all"
                    title="Delete Note"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Reader Scrollable Body */}
              <div className="flex-1 p-4 sm:p-6 overflow-y-auto">
                {loadingDetail ? (
                  <div className="flex items-center justify-center h-48 text-[#41e6ff] font-mono text-xs gap-2">
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Loading Markdown document...</span>
                  </div>
                ) : (
                  <MarkdownRenderer content={selectedNote.content} />
                )}
              </div>
            </div>
          ) : (
            /* Case 3: Empty State */
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-[#7da4b8]">
              <div className="p-4 rounded-full bg-[rgba(65,230,255,0.06)] border border-[rgba(65,230,255,0.2)] text-[#41e6ff] mb-3 shadow-[0_0_15px_rgba(65,230,255,0.15)]">
                <BookOpen size={36} />
              </div>
              <h4 className="font-display text-sm sm:text-base font-bold tracking-wider text-[#e8fbff]">
                SELECT A NOTE TO INSPECT
              </h4>
              <p className="font-mono text-[11px] text-[#7da4b8] max-w-sm mt-1">
                Choose a research report, general note, or checklist from the repository explorer on the left.
              </p>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={startNewNote}
                  className="px-3 py-1.5 rounded-lg bg-[rgba(65,230,255,0.15)] border border-[#41e6ff] text-[#41e6ff] font-mono text-xs font-bold hover:bg-[rgba(65,230,255,0.3)] shadow-[0_0_10px_rgba(65,230,255,0.3)] flex items-center gap-1.5"
                >
                  <Plus size={13} />
                  <span>CREATE NOTE</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
