import { useState, useMemo, memo } from 'react'
import { useMcp } from '../hooks/useMcp'
import { soundFx } from '../lib/soundFx'
import type { McpCatalogItem } from '../types'
import {
  Cpu,
  RefreshCw,
  Plus,
  Trash2,
  RotateCw,
  Search,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Terminal,
  CloudSun,
  BookOpen,
  Globe,
  Compass,
  GitBranch,
  Wrench,
  Sparkles,
  Sliders,
  Send,
  X,
  ShieldCheck,
  Smartphone,
} from 'lucide-react'

const ICON_MAP: Record<string, typeof Terminal> = {
  CloudSun,
  BookOpen,
  Terminal,
  Globe,
  Compass,
  GitBranch,
  Wrench,
  Search,
  ShieldCheck,
  Smartphone,
}

interface Props {
  onSendPrompt?: (text: string) => void
  onClose?: () => void
}

export const McpConfigPanel = memo(function McpConfigPanel({ onSendPrompt, onClose }: Props) {
  const { data, loading, error, refresh, toggleServer, restartServer, saveServer, deleteServer } = useMcp()
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedServers, setExpandedServers] = useState<Record<string, boolean>>({})
  const [showAddModal, setShowAddModal] = useState(false)
  const [modalMode, setModalMode] = useState<'custom' | 'catalog'>('custom')
  const [selectedCatalogItem, setSelectedCatalogItem] = useState<McpCatalogItem | null>(null)

  // Add / Edit form fields
  const [formName, setFormName] = useState('')
  const [formCommand, setFormCommand] = useState('.venv/bin/python3')
  const [formArgs, setFormArgs] = useState('')
  const [formEnv, setFormEnv] = useState('')
  const [formError, setFormError] = useState('')

  const servers = data?.servers || []
  const catalog = data?.catalog || []

  const toggleExpand = (name: string) => {
    soundFx.click()
    setExpandedServers((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  const filteredServers = useMemo(() => {
    if (!searchQuery.trim()) return servers
    const q = searchQuery.toLowerCase().trim()
    return servers.filter((s) => {
      if (s.name.toLowerCase().includes(q)) return true
      if (s.command.toLowerCase().includes(q)) return true
      if (s.tools.some((t) => t.name.toLowerCase().includes(q) || (t.description && t.description.toLowerCase().includes(q))))
        return true
      return false
    })
  }, [servers, searchQuery])

  const openAddModalForCustom = () => {
    soundFx.click()
    setModalMode('custom')
    setSelectedCatalogItem(null)
    setFormName('')
    setFormCommand('.venv/bin/python3')
    setFormArgs('')
    setFormEnv('')
    setFormError('')
    setShowAddModal(true)
  }

  const openAddModalForCatalog = (item: McpCatalogItem) => {
    soundFx.click()
    setModalMode('catalog')
    setSelectedCatalogItem(item)
    setFormName(item.id)
    setFormCommand(item.command)
    setFormArgs(item.args.join(' '))
    setFormEnv(JSON.stringify(item.env || {}, null, 2))
    setFormError('')
    setShowAddModal(true)
  }

  const handleSaveModal = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formName.trim()) {
      setFormError('Server ID / Name is required')
      return
    }
    if (!formCommand.trim()) {
      setFormError('Command executable is required')
      return
    }

    let parsedEnv = {}
    if (formEnv.trim()) {
      try {
        parsedEnv = JSON.parse(formEnv)
      } catch {
        setFormError('Environment variables must be a valid JSON object (e.g. {"KEY": "VALUE"})')
        return
      }
    }

    const argsList = formArgs
      .trim()
      .split(/\s+/)
      .filter((a) => a.length > 0)

    const ok = await saveServer(formName.trim(), {
      command: formCommand.trim(),
      args: argsList,
      env: parsedEnv,
      enabled: true,
    })

    if (ok) {
      setShowAddModal(false)
    } else {
      setFormError('Failed to save server configuration.')
    }
  }

  const handleTestQuery = (query: string) => {
    soundFx.click()
    if (onSendPrompt) {
      onSendPrompt(query)
    }
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-[rgba(3,7,12,0.85)] p-3 sm:p-5 md:p-6 space-y-5">
      {/* Header telemetry and stats */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 border-b border-[rgba(65,230,255,0.18)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-[rgba(65,230,255,0.1)] border border-[rgba(65,230,255,0.3)]">
              <Sliders size={18} className="text-[#41e6ff]" />
            </div>
            <h1 className="font-display text-lg sm:text-xl font-bold tracking-[0.2em] text-[#e8fbff]">
              MCP MODULE MATRIX
            </h1>
            <span className="font-mono text-[9px] tracking-widest text-[#41e6ff] bg-[rgba(65,230,255,0.08)] px-2 py-0.5 rounded border border-[rgba(65,230,255,0.2)]">
              JSON-RPC 2.0
            </span>
          </div>
          <p className="font-mono text-[10px] sm:text-[11px] tracking-wider text-[#7da4b8] mt-1">
            Dynamic Model Context Protocol supervision — enable, calibrate, or hot-swap tools for A.T.H.E.N.A.
          </p>
        </div>

        {/* Quick stats and action bar */}
        <div className="flex flex-wrap items-center gap-2 self-stretch md:self-auto">
          <div className="flex items-center gap-3 bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] px-3 py-1.5 rounded font-mono text-[10px]">
            <div className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-[#41e6ff] shadow-[0_0_8px_#41e6ff]" />
              <span className="text-[#7da4b8]">ACTIVE:</span>
              <strong className="text-[#e8fbff]">{data?.active_servers ?? 0} / {servers.length}</strong>
            </div>
            <div className="border-l border-[rgba(65,230,255,0.15)] pl-3 flex items-center gap-1.5">
              <Sparkles size={11} className="text-[#ffc24b]" />
              <span className="text-[#7da4b8]">TOOLS:</span>
              <strong className="text-[#ffc24b]">{data?.total_tools ?? 0}</strong>
            </div>
          </div>

          <button
            onClick={() => refresh()}
            disabled={loading}
            title="Scan & Refresh MCP Status"
            className="flex items-center gap-1.5 bg-[rgba(65,230,255,0.06)] hover:bg-[rgba(65,230,255,0.15)] border border-[rgba(65,230,255,0.25)] text-[#41e6ff] px-2.5 py-1.5 rounded font-mono text-[10px] tracking-wider transition-all disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            <span className="hidden xs:inline">RELOAD</span>
          </button>

          <button
            onClick={openAddModalForCustom}
            className="flex items-center gap-1.5 bg-[rgba(65,230,255,0.15)] hover:bg-[rgba(65,230,255,0.25)] border border-[#41e6ff] text-[#e8fbff] px-3 py-1.5 rounded font-mono text-[10px] tracking-wider transition-all shadow-[0_0_12px_rgba(65,230,255,0.25)] hover:shadow-[0_0_16px_rgba(65,230,255,0.4)]"
          >
            <Plus size={13} className="text-[#41e6ff]" />
            <span>ADD MCP</span>
          </button>

          {onClose && (
            <button
              onClick={() => {
                soundFx.click()
                onClose()
              }}
              className="p-1.5 text-[#7da4b8] hover:text-[#ff5d5d] rounded transition-colors md:hidden"
              title="Close panel"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Error alert if any */}
      {error && (
        <div className="bg-[rgba(255,93,93,0.1)] border border-[rgba(255,93,93,0.4)] text-[#ff5d5d] p-3 rounded font-mono text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle size={15} />
            <span>{error}</span>
          </div>
          <button onClick={() => refresh()} className="underline hover:text-white text-[10px]">
            Retry
          </button>
        </div>
      )}

      {/* Search & filter bar */}
      <div className="relative w-full max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#7da4b8]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter MCP servers or tools (e.g. weather, notes, calculate)..."
          className="w-full bg-[rgba(6,14,21,0.7)] border border-[rgba(65,230,255,0.2)] focus:border-[#41e6ff] text-xs font-mono text-[#e8fbff] pl-9 pr-3 py-2 rounded outline-none transition-colors placeholder:text-[#3e5c6d]"
        />
      </div>

      {/* Section 1: Configured MCP Servers */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs tracking-[0.2em] text-[#41e6ff] flex items-center gap-1.5">
            <Cpu size={14} />
            <span>CONFIGURED MCP SERVERS ({filteredServers.length})</span>
          </span>
          <span className="font-mono text-[9px] text-[#7da4b8]">
            TOGGLE TO ENABLE/DISABLE ON THE FLY
          </span>
        </div>

        {filteredServers.length === 0 ? (
          <div className="border border-dashed border-[rgba(65,230,255,0.2)] rounded-lg p-6 text-center font-mono text-xs text-[#7da4b8]">
            No matching MCP servers found. Use the catalog below to add modules or create a custom one.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {filteredServers.map((server) => {
              const isExpanded = !!expandedServers[server.name]
              const isDummyDemo = server.name === 'dummy-demo'
              const isNotes = server.name === 'notes-memory'
              const isOpencode = server.name === 'opencode'

              return (
                <div
                  key={server.name}
                  className={`rounded-lg border transition-all duration-300 ${
                    server.running
                      ? 'border-[rgba(65,230,255,0.35)] bg-[rgba(6,14,21,0.85)] shadow-[0_0_15px_rgba(65,230,255,0.06)]'
                      : server.enabled
                        ? 'border-[rgba(255,194,75,0.4)] bg-[rgba(15,12,6,0.75)]'
                        : 'border-[rgba(65,230,255,0.1)] bg-[rgba(4,9,15,0.6)] opacity-75'
                  }`}
                >
                  {/* Card Header & Controls */}
                  <div className="p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start sm:items-center gap-3">
                      {/* Category Icon */}
                      <div
                        className={`p-2 rounded border ${
                          server.running
                            ? 'border-[#41e6ff] bg-[rgba(65,230,255,0.15)] text-[#41e6ff]'
                            : 'border-[rgba(65,230,255,0.15)] bg-[rgba(65,230,255,0.05)] text-[#7da4b8]'
                        }`}
                      >
                        {isDummyDemo ? (
                          <CloudSun size={20} />
                        ) : isNotes ? (
                          <BookOpen size={20} />
                        ) : isOpencode ? (
                          <Terminal size={20} />
                        ) : (
                          <Wrench size={20} />
                        )}
                      </div>

                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-display text-sm sm:text-base font-bold tracking-wider text-[#e8fbff]">
                            {server.name}
                          </span>

                          {/* Status Pill */}
                          <span
                            className={`font-mono text-[8.5px] px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                              server.running
                                ? 'border-[#41e6ff] bg-[rgba(65,230,255,0.12)] text-[#41e6ff]'
                                : server.enabled
                                  ? 'border-[#ffc24b] bg-[rgba(255,194,75,0.12)] text-[#ffc24b]'
                                  : 'border-[#3e5c6d] bg-[rgba(62,92,109,0.12)] text-[#7da4b8]'
                            }`}
                          >
                            <span
                              className={`size-1.5 rounded-full ${
                                server.running
                                  ? 'bg-[#41e6ff] shadow-[0_0_6px_#41e6ff]'
                                  : server.enabled
                                    ? 'bg-[#ffc24b]'
                                    : 'bg-[#3e5c6d]'
                              }`}
                            />
                            <span>{server.running ? 'ONLINE' : server.enabled ? 'INITIALIZING' : 'DISABLED'}</span>
                          </span>

                          <span className="font-mono text-[9px] text-[#ffc24b] bg-[rgba(255,194,75,0.08)] px-1.5 py-0.5 rounded">
                            {server.tools_count} {server.tools_count === 1 ? 'Tool' : 'Tools'}
                          </span>
                        </div>

                        <div className="font-mono text-[9.5px] text-[#7da4b8] mt-0.5 flex items-center gap-2 truncate max-w-xs sm:max-w-md">
                          <code className="text-[#38ef7d] bg-[rgba(56,239,125,0.05)] px-1 rounded">
                            {server.command} {server.args.join(' ')}
                          </code>
                        </div>
                      </div>
                    </div>

                    {/* Right action switches & buttons */}
                    <div className="flex items-center gap-2 self-end sm:self-auto">
                      {/* Enable / Disable Toggle Switch */}
                      <button
                        onClick={() => toggleServer(server.name, !server.enabled)}
                        title={server.enabled ? 'Click to Disable MCP Server' : 'Click to Enable MCP Server'}
                        className={`relative inline-flex h-6 w-12 items-center rounded-full transition-colors focus:outline-none ${
                          server.enabled
                            ? 'bg-[#41e6ff] shadow-[0_0_12px_rgba(65,230,255,0.6)]'
                            : 'bg-[rgba(62,92,109,0.4)]'
                        }`}
                      >
                        <span
                          className={`inline-block size-4 transform rounded-full bg-[#03070b] transition-transform ${
                            server.enabled ? 'translate-x-7' : 'translate-x-1'
                          }`}
                        />
                      </button>

                      {/* Restart */}
                      <button
                        onClick={() => restartServer(server.name)}
                        disabled={!server.enabled}
                        title="Restart MCP Process"
                        className="p-1.5 text-[#7da4b8] hover:text-[#41e6ff] bg-[rgba(65,230,255,0.05)] hover:bg-[rgba(65,230,255,0.12)] border border-[rgba(65,230,255,0.15)] rounded transition-all disabled:opacity-30"
                      >
                        <RotateCw size={13} />
                      </button>

                      {/* Delete */}
                      <button
                        onClick={() => {
                          if (confirm(`Are you sure you want to remove MCP server '${server.name}'?`)) {
                            deleteServer(server.name)
                          }
                        }}
                        title="Remove MCP Server"
                        className="p-1.5 text-[#7da4b8] hover:text-[#ff5d5d] bg-[rgba(255,93,93,0.05)] hover:bg-[rgba(255,93,93,0.15)] border border-[rgba(255,93,93,0.2)] rounded transition-all"
                      >
                        <Trash2 size={13} />
                      </button>

                      {/* Expand / Collapse Tool Drawer */}
                      <button
                        onClick={() => toggleExpand(server.name)}
                        className="p-1.5 text-[#7da4b8] hover:text-[#e8fbff] bg-[rgba(65,230,255,0.05)] border border-[rgba(65,230,255,0.15)] rounded transition-all"
                        title={isExpanded ? 'Collapse Tools' : 'Inspect Registered Tools'}
                      >
                        {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>
                    </div>
                  </div>

                  {/* Expandable Tools List & Schema Inspection */}
                  {isExpanded && (
                    <div className="border-t border-[rgba(65,230,255,0.1)] bg-[rgba(3,7,12,0.6)] p-3 sm:p-4 space-y-2.5">
                      <div className="font-mono text-[9px] tracking-wider text-[#41e6ff] flex items-center justify-between">
                        <span>DYNAMIC REGISTERED TOOLS ({server.tools.length}):</span>
                        {server.server_info?.name && (
                          <span className="text-[#7da4b8]">
                            SERVER PROTOCOL: {server.server_info.name} v{server.server_info.version || '1.0'}
                          </span>
                        )}
                      </div>

                      {server.tools.length === 0 ? (
                        <p className="font-mono text-[10px] text-[#7da4b8] italic">
                          {server.enabled
                            ? 'Server is running or initializing, but no tools have been returned yet.'
                            : 'Server is currently disabled. Toggle switch above to activate tools.'}
                        </p>
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                          {server.tools.map((tool) => (
                            <div
                              key={tool.name}
                              className="rounded border border-[rgba(65,230,255,0.12)] bg-[rgba(6,14,21,0.6)] p-2.5 hover:border-[rgba(65,230,255,0.3)] transition-colors"
                            >
                              <div className="flex items-center justify-between gap-1 mb-1">
                                <span className="font-mono text-xs font-bold text-[#38ef7d] flex items-center gap-1.5">
                                  <Terminal size={11} className="text-[#41e6ff]" />
                                  <span>{tool.name}</span>
                                </span>

                                {/* Quick query test button */}
                                {tool.name === 'mcp_get_weather' && (
                                  <button
                                    onClick={() =>
                                      handleTestQuery('Athena, what is the weather in Chennai, Tamil Nadu, India according to the MCP weather tool?')
                                    }
                                    className="font-mono text-[8.5px] text-[#41e6ff] hover:text-white bg-[rgba(65,230,255,0.1)] hover:bg-[rgba(65,230,255,0.2)] px-1.5 py-0.5 rounded border border-[rgba(65,230,255,0.2)] flex items-center gap-1"
                                    title="Run Chennai weather test prompt"
                                  >
                                    <Send size={8} />
                                    <span>Chennai Weather</span>
                                  </button>
                                )}

                                {tool.name === 'notes_list_notes' && (
                                  <button
                                    onClick={() => handleTestQuery('Athena, list all my saved notes from user memory.')}
                                    className="font-mono text-[8.5px] text-[#41e6ff] hover:text-white bg-[rgba(65,230,255,0.1)] hover:bg-[rgba(65,230,255,0.2)] px-1.5 py-0.5 rounded border border-[rgba(65,230,255,0.2)] flex items-center gap-1"
                                    title="List notes prompt"
                                  >
                                    <Send size={8} />
                                    <span>List Notes</span>
                                  </button>
                                )}
                              </div>

                              <p className="font-mono text-[9.5px] text-[#7da4b8] leading-relaxed">
                                {tool.description || 'No tool description provided.'}
                              </p>

                              {/* Schema params */}
                              {tool.inputSchema?.properties &&
                                Object.keys(tool.inputSchema.properties).length > 0 && (
                                  <div className="mt-1.5 pt-1.5 border-t border-[rgba(65,230,255,0.06)] flex flex-wrap items-center gap-1">
                                    <span className="font-mono text-[8px] text-[#3e5c6d]">PARAMS:</span>
                                    {Object.entries(tool.inputSchema.properties).map(([paramName, paramSpec]) => (
                                      <span
                                        key={paramName}
                                        className="font-mono text-[8px] bg-[rgba(65,230,255,0.06)] text-[#7da4b8] px-1 py-0.5 rounded border border-[rgba(65,230,255,0.1)]"
                                        title={paramSpec.description || ''}
                                      >
                                        {paramName}
                                        <span className="text-[#3e5c6d]">:{paramSpec.type || 'any'}</span>
                                      </span>
                                    ))}
                                  </div>
                                )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Section 2: Curated Everyday User MCP Library */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs tracking-[0.2em] text-[#ffc24b] flex items-center gap-1.5">
            <Sparkles size={14} />
            <span>RECOMMENDED MCP MODULES FOR EVERYDAY USERS</span>
          </span>
          <span className="font-mono text-[9px] text-[#7da4b8]">
            1-CLICK INSTALL & CONFIGURE
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {catalog.map((item) => {
            const Icon = ICON_MAP[item.icon] || Wrench
            const isInstalled = servers.some((s) => s.name === item.id)

            return (
              <div
                key={item.id}
                className="rounded-lg border border-[rgba(65,230,255,0.18)] bg-[rgba(6,14,21,0.7)] p-3.5 flex flex-col justify-between hover:border-[rgba(65,230,255,0.35)] transition-all group"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded bg-[rgba(65,230,255,0.1)] text-[#41e6ff] border border-[rgba(65,230,255,0.2)]">
                        <Icon size={16} />
                      </div>
                      <span className="font-display text-sm font-bold text-[#e8fbff] tracking-wide">
                        {item.name}
                      </span>
                    </div>

                    <span className="font-mono text-[8px] tracking-wider uppercase text-[#7da4b8] bg-[rgba(65,230,255,0.06)] px-1.5 py-0.5 rounded border border-[rgba(65,230,255,0.1)]">
                      {item.category}
                    </span>
                  </div>

                  <p className="font-mono text-[10px] text-[#7da4b8] leading-relaxed mb-3">
                    {item.description}
                  </p>
                </div>

                <div className="pt-2 border-t border-[rgba(65,230,255,0.08)] flex items-center justify-between">
                  <span className="font-mono text-[8.5px] text-[#3e5c6d]">
                    ID: {item.id}
                  </span>

                  {isInstalled ? (
                    <span className="font-mono text-[9px] text-[#38ef7d] flex items-center gap-1 bg-[rgba(56,239,125,0.1)] px-2 py-0.5 rounded border border-[rgba(56,239,125,0.25)]">
                      <CheckCircle2 size={10} />
                      <span>INSTALLED</span>
                    </span>
                  ) : (
                    <button
                      onClick={() => openAddModalForCatalog(item)}
                      className="font-mono text-[9.5px] text-[#41e6ff] hover:text-white bg-[rgba(65,230,255,0.1)] hover:bg-[rgba(65,230,255,0.2)] border border-[rgba(65,230,255,0.3)] px-2.5 py-1 rounded transition-all flex items-center gap-1 shadow-[0_0_8px_rgba(65,230,255,0.15)]"
                    >
                      <Plus size={10} />
                      <span>ADD MODULE</span>
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Add / Edit MCP Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-3 sm:p-4">
          <div className="w-full max-w-lg rounded-xl border border-[rgba(65,230,255,0.3)] bg-[rgba(5,11,18,0.95)] p-4 sm:p-6 shadow-[0_0_30px_rgba(65,230,255,0.2)] space-y-4">
            <div className="flex items-center justify-between border-b border-[rgba(65,230,255,0.15)] pb-3">
              <div className="flex items-center gap-2">
                <Sliders size={16} className="text-[#41e6ff]" />
                <h3 className="font-display text-base font-bold tracking-wider text-[#e8fbff]">
                  {modalMode === 'catalog' ? `CONFIGURE ${selectedCatalogItem?.name.toUpperCase()}` : 'REGISTER CUSTOM MCP SERVER'}
                </h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[#7da4b8] hover:text-[#ff5d5d] transition-colors p-1"
              >
                <X size={16} />
              </button>
            </div>

            {formError && (
              <div className="p-2.5 rounded bg-[rgba(255,93,93,0.1)] border border-[rgba(255,93,93,0.3)] text-[#ff5d5d] font-mono text-xs">
                {formError}
              </div>
            )}

            <form onSubmit={handleSaveModal} className="space-y-3">
              <div>
                <label className="block font-mono text-[10px] text-[#41e6ff] tracking-wider mb-1">
                  SERVER IDENTIFIER (Unique ID)
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. weather-service, math-mcp, my-tools"
                  className="w-full rounded bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] px-3 py-1.5 font-mono text-xs text-[#e8fbff] focus:border-[#41e6ff] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] text-[#41e6ff] tracking-wider mb-1">
                  COMMAND / EXECUTABLE
                </label>
                <input
                  type="text"
                  value={formCommand}
                  onChange={(e) => setFormCommand(e.target.value)}
                  placeholder="e.g. .venv/bin/python3, python3, npx, node"
                  className="w-full rounded bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] px-3 py-1.5 font-mono text-xs text-[#e8fbff] focus:border-[#41e6ff] outline-none"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] text-[#41e6ff] tracking-wider mb-1">
                  COMMAND ARGUMENTS (Space separated)
                </label>
                <input
                  type="text"
                  value={formArgs}
                  onChange={(e) => setFormArgs(e.target.value)}
                  placeholder="e.g. dummy_mcp_server.py or -y @modelcontextprotocol/server-brave-search"
                  className="w-full rounded bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] px-3 py-1.5 font-mono text-xs text-[#e8fbff] focus:border-[#41e6ff] outline-none"
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] text-[#41e6ff] tracking-wider mb-1">
                  ENVIRONMENT VARIABLES (JSON format)
                </label>
                <textarea
                  value={formEnv}
                  onChange={(e) => setFormEnv(e.target.value)}
                  placeholder='e.g. {"BRAVE_API_KEY": "${BRAVE_API_KEY}", "DEBUG": "1"}'
                  rows={3}
                  className="w-full rounded bg-[rgba(6,14,21,0.8)] border border-[rgba(65,230,255,0.2)] px-3 py-1.5 font-mono text-xs text-[#e8fbff] focus:border-[#41e6ff] outline-none font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[rgba(65,230,255,0.15)]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded font-mono text-xs text-[#7da4b8] hover:text-white bg-[rgba(65,230,255,0.05)] border border-[rgba(65,230,255,0.1)] transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded font-mono text-xs text-[#03070b] font-bold bg-[#41e6ff] hover:bg-[#7ef3ff] transition-all shadow-[0_0_12px_rgba(65,230,255,0.5)]"
                >
                  Save & Initialize Server
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
})
