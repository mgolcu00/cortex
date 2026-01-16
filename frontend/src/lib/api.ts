import type {
  Session,
  SessionDetail,
  ChatResponse,
  Stats,
  HealthStatus,
  Page,
  PageDetail,
  Space,
  Instructions,
} from '@/types'

const API_BASE = ''

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }

  return res.json()
}

// Health
export async function getHealth(): Promise<HealthStatus> {
  return fetchJSON('/health')
}

// Stats
export async function getStats(): Promise<Stats> {
  return fetchJSON('/api/stats')
}

// Sessions
export async function getSessions(): Promise<Session[]> {
  return fetchJSON('/sessions')
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return fetchJSON(`/sessions/${sessionId}`)
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetchJSON(`/sessions/${sessionId}`, { method: 'DELETE' })
}

// Chat
export async function sendMessage(
  message: string,
  sessionId?: string | null
): Promise<ChatResponse> {
  return fetchJSON('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  })
}

// Database
export async function getPages(params: {
  limit?: number
  offset?: number
  space?: string
  search?: string
}): Promise<{ total: number; pages: Page[] }> {
  const searchParams = new URLSearchParams()
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())
  if (params.space) searchParams.set('space', params.space)
  if (params.search) searchParams.set('search', params.search)

  return fetchJSON(`/api/db/pages?${searchParams}`)
}

export async function getPageDetail(pageId: string): Promise<PageDetail> {
  return fetchJSON(`/api/db/pages/${pageId}`)
}

export async function getSpaces(): Promise<{ spaces: Space[] }> {
  return fetchJSON('/api/db/spaces')
}

// Sync
export async function runSync(mode: 'full' | 'incremental' = 'incremental'): Promise<{ status: string; mode: string }> {
  return fetchJSON('/sync/run', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export async function getSyncStatus(): Promise<{
  last_run_at: string | null
  last_run_success: boolean | null
  pages_synced: number
  chunks_created: number
}> {
  return fetchJSON('/sync/status')
}

// Instructions
export async function getInstructions(): Promise<Instructions> {
  return fetchJSON('/api/instructions')
}

export async function updateInstructions(instructions: string): Promise<{ success: boolean; message: string }> {
  return fetchJSON('/api/instructions', {
    method: 'PUT',
    body: JSON.stringify({ instructions }),
  })
}

export async function resetInstructions(): Promise<{ success: boolean; message: string }> {
  return fetchJSON('/api/instructions/reset', {
    method: 'POST',
  })
}

// Config
export interface AppConfig {
  openai: {
    chat_model: string
    embedding_model: string
    embedding_dimensions: number
    api_key_set: boolean
  }
  confluence: {
    base_url: string
    email: string
    api_token_set: boolean
  }
  database: {
    url_set: boolean
    url_preview: string
  }
  sync: {
    interval_minutes: number
    batch_size: number
  }
  chunking: {
    target_tokens: number
    min_tokens: number
    max_tokens: number
    overlap_tokens: number
  }
  search: {
    top_k: number
    max_pages: number
  }
  log_level: string
}

export async function getConfig(): Promise<AppConfig> {
  return fetchJSON('/api/config')
}

// Feedback
export async function submitFeedback(
  sessionId: string,
  messageIndex: number,
  feedback: 'like' | 'dislike',
  comment?: string
): Promise<{ success: boolean; message: string }> {
  return fetchJSON('/api/feedback', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      message_index: messageIndex,
      feedback,
      comment,
    }),
  })
}

export async function getSessionFeedback(
  sessionId: string
): Promise<{ feedbacks: Record<number, 'like' | 'dislike'> }> {
  return fetchJSON(`/api/feedback/${sessionId}`)
}

export async function deleteFeedback(
  sessionId: string,
  messageIndex: number
): Promise<{ success: boolean; message: string }> {
  return fetchJSON(`/api/feedback?session_id=${sessionId}&message_index=${messageIndex}`, {
    method: 'DELETE',
  })
}

// Conversation Starters
import type { StarterItem, Starters } from '@/types'

export async function getStarters(): Promise<Starters> {
  return fetchJSON('/api/starters')
}

export async function updateStarters(
  starters: StarterItem[]
): Promise<{ success: boolean; message: string }> {
  return fetchJSON('/api/starters', {
    method: 'PUT',
    body: JSON.stringify({ starters }),
  })
}

export async function resetStarters(): Promise<{ success: boolean; message: string }> {
  return fetchJSON('/api/starters/reset', {
    method: 'POST',
  })
}
