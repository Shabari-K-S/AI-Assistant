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
  since: number
}

export interface LogLine {
  id: string
  kind: 'log' | 'transcript' | 'reply' | 'error' | 'command'
  level?: string
  msg?: string
  text?: string
  confidence?: number
  t: number
}

export const DEFAULT_SNAPSHOT: Snapshot = {
  online: false,
  phase: 'standby',
  wake_score: 0,
  threshold: 0.5,
  noise_floor: 0,
  muted: false,
  wake_word: 'SARA',
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
  new URLSearchParams(window.location.search).get('bridge') ?? '/bridge'

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
  servers: McpServerConfig[]
  catalog: McpCatalogItem[]
  total_tools: number
  active_servers: number
}

