export interface Session {
  id: string
  title: string
  started_at: string
  last_message: string
  message_count: number
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  stats?: MessageStats
  timestamp?: string
}

export interface Source {
  title: string
  url: string
}

export interface MessageStats {
  duration_ms: number
  tokens: {
    prompt: number
    completion: number
    total: number
  }
  api_calls: {
    confluence: number
    database: number
    embedding: number
  }
  tool_calls: ToolCall[]
  used_search: boolean
  estimated_cost_usd: number
}

export interface ToolCall {
  tool: string
  args: Record<string, string>
  result_preview: string
}

export interface ChatResponse {
  success: boolean
  session_id: string
  answer?: string
  sources?: Source[]
  stats?: MessageStats
  error?: string
}

export interface SessionDetail {
  id: string
  title: string
  messages: Message[]
  usage?: {
    total_messages: number
    total_tokens: number
    total_cost_usd: number
  }
}

export interface Stats {
  usage: {
    total_requests: number
    total_tokens: number
    total_cost_usd: number
    total_confluence_requests: number
    total_db_requests: number
  }
  database: {
    pages: number
    chunks: number
    last_sync: string | null
    last_sync_success: boolean | null
  }
}

export interface HealthStatus {
  status: string
  database: string
  confluence: string
}

export interface Page {
  page_id: string
  title: string
  space_key: string
  url: string
  version: number
  updated_at: string | null
  synced_at: string | null
  chunk_count: number
}

export interface PageDetail extends Omit<Page, 'chunk_count'> {
  body_text: string | null
  chunks: Chunk[]
}

export interface Chunk {
  chunk_id: string
  chunk_index: number
  heading_path: string | null
  text: string
  token_count: number | null
}

export interface Space {
  space_key: string
  page_count: number
}

export interface Instructions {
  current: string
  default: string
  is_default: boolean
}
