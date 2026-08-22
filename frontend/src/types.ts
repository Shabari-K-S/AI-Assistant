export type Phase = 'standby' | 'listening' | 'processing' | 'speaking'

export interface Snapshot {
  online: boolean
  phase: Phase
  wake_score: number
  threshold: number
  noise_floor: number
  muted: boolean
  wake_word: string
  stt_model: string
  llm_model: string
  tts: string
  transcript: string
  reply: string
  active_tool?: { name: string; args?: Record<string, unknown>; started_at?: number } | null
  last_tool_result?: { name: string; duration_ms: number; status: string; preview: string } | null
  last_inference?: { model: string; ttft_ms: number; total_ms: number; chars: number } | null
  memory_stats?: { query: string; facts_count: number; notes_count: number; recalled_items: string[] } | null
  since: number
}

export interface LogLine {
  id: string
  kind: 'log' | 'transcript' | 'reply' | 'error' | 'command' | 'tool' | 'memory' | 'llm'
  level?: string
  msg?: string
  text?: string
  confidence?: number
  toolData?: {
    name: string
    args?: Record<string, unknown>
    duration_ms?: number
    status?: string
    preview?: string
  }
  memoryData?: {
    query?: string
    facts?: Array<{ id?: string; text?: string; category?: string; score?: number }>
    notes?: Array<{ title?: string; heading?: string; category?: string; score?: number; file_path?: string }>
  }
  llmData?: {
    model?: string
    ttft_ms?: number
    total_ms?: number
    chars?: number
  }
  t: number
}

export interface DeepResearchState {
  active: boolean
  topic?: string
  stage?: string
  step?: number
  total?: number
  file?: string
}

export const DEFAULT_SNAPSHOT: Snapshot = {
  online: false,
  phase: 'standby',
  wake_score: 0,
  threshold: 0.5,
  noise_floor: 0,
  muted: false,
  wake_word: 'ATHENA',
  stt_model: 'WHISPER',
  llm_model: 'GEMMA-4',
  tts: 'PIPER',
  transcript: '',
  reply: '',
  since: 0,
}

/**
 * Bridge endpoint. Default: same-origin `/bridge`, proxied by Vite to the
 * assistant's evbridge server on :2027 (works from any browser host).
 * Override with ?bridge=http://host:port.
 */
export const BRIDGE_URL =
  new URLSearchParams(window.location.search).get('bridge') ??
  (window.location.port === '2026' ? '/bridge' : '')

export interface McpTool {
  name: string
  description?: string
  inputSchema?: {
    type?: string
    properties?: Record<string, { type?: string; description?: string }>
    required?: string[]
  }
}

export interface McpServerInfo {
  name?: string
  version?: string
}

export interface McpServerConfig {
  name: string
  command: string
  args: string[]
  env?: Record<string, string>
  enabled: boolean
  running: boolean
  tools_count: number
  tools: McpTool[]
  server_info?: McpServerInfo
  error?: string
}

export interface McpCatalogItem {
  id: string
  name: string
  description: string
  category: 'utilities' | 'productivity' | 'developer' | 'search'
  icon: string
  command: string
  args: string[]
  env?: Record<string, string>
  preinstalled: boolean
}

export interface McpStatusResponse {
  ok: boolean
  config_path?: string
  athena_home?: string
  servers: McpServerConfig[]
  catalog: McpCatalogItem[]
  total_tools: number
  active_servers: number
}

export interface McpDiscoveryResult {
  ok: boolean
  source?: string
  id?: string
  name?: string
  description?: string
  package?: string
  command?: string
  args?: string[]
  env?: Record<string, string>
  required_env?: string[]
  required_args?: string[]
  clarification_needed?: boolean
  clarification_prompt?: string
  error?: string
  candidates?: Array<{
    name: string
    description: string
    version: string
  }>
}

export interface VaultNote {
  id: string
  title: string
  category: string
  path: string
  created_at: string
  preview: string
  tags?: string[]
  sources_count?: number
  model_used?: string
}

export interface VaultIndexResponse {
  updated_at: string
  vault_path: string
  notes: VaultNote[]
}

export interface VaultNoteDetail {
  ok: boolean
  id: string
  title: string
  category: string
  path: string
  created_at: string
  updated_at?: string
  tags?: string[]
  sources_count?: number
  model_used?: string
  content: string
}

export interface ActiveTimer {
  id: string
  label: string
  timer_type: 'timer' | 'pomodoro' | 'break' | 'reminder'
  total_seconds: number
  remaining_seconds: number
  progress_percent: number
  created_at: string
  expires_at: number
  status: 'running' | 'expired' | 'cancelled'
  is_reminder?: boolean
}

export interface DailyBriefing {
  ok: boolean
  type: 'morning' | 'evening'
  date: string
  time: string
  weather: {
    city: string
    temp_c: number
    temp_f: number
    condition: string
    wind_kph: number
    summary: string
  }
  todos: {
    pending: string[]
    completed: string[]
    pending_count: number
    completed_count: number
  }
  news: {
    title: string
    source: string
    url: string
    snippet: string
  }[]
  telemetry: {
    cpu_percent: number
    memory_percent: number
    memory_used_gb: number
    memory_total_gb: number
    battery: string
    hostname: string
    os: string
  }
  spoken_summary: string
  markdown_report: string
}


