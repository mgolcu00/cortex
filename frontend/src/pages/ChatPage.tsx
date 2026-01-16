import { useEffect, useState, useRef } from 'react'
import { Plus, Send, Trash2, MessageSquare, ExternalLink, ArrowUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useStore } from '@/lib/store'
import * as api from '@/lib/api'
import { formatDate, generateId, truncate } from '@/lib/utils'
import type { Message, Session } from '@/types'

export function ChatPage() {
  const {
    currentSessionId,
    setCurrentSessionId,
    sessions,
    setSessions,
    messages,
    setMessages,
    addMessage,
    isLoading,
    setLoading,
    reset,
  } = useStore()

  const [input, setInput] = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    loadSessions()
  }, [])

  useEffect(() => {
    if (currentSessionId) {
      loadSessionMessages(currentSessionId)
    } else {
      setMessages([])
    }
  }, [currentSessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  async function loadSessions() {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }

  async function loadSessionMessages(sessionId: string) {
    try {
      const session = await api.getSession(sessionId)
      setMessages(session.messages)
    } catch (error) {
      console.error('Failed to load session:', error)
      setCurrentSessionId(null)
    }
  }

  // Simulate streaming effect
  function simulateStreaming(text: string, onComplete: () => void) {
    setIsStreaming(true)
    setStreamingText('')

    const words = text.split(' ')
    let currentIndex = 0

    const interval = setInterval(() => {
      if (currentIndex < words.length) {
        setStreamingText(prev => prev + (currentIndex > 0 ? ' ' : '') + words[currentIndex])
        currentIndex++
      } else {
        clearInterval(interval)
        setIsStreaming(false)
        setStreamingText('')
        onComplete()
      }
    }, 30) // 30ms per word for natural feel
  }

  async function handleSend() {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    }

    const messageToSend = input.trim()
    setInput('')
    addMessage(userMessage)
    setLoading(true)

    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }

    try {
      const response = await api.sendMessage(
        messageToSend,
        currentSessionId || generateId()
      )

      if (response.success) {
        setCurrentSessionId(response.session_id)

        const assistantMessage: Message = {
          role: 'assistant',
          content: response.answer || '',
          sources: response.sources,
          stats: response.stats,
        }

        // Simulate streaming
        simulateStreaming(response.answer || '', () => {
          addMessage(assistantMessage)
          loadSessions()
        })
      } else {
        addMessage({
          role: 'assistant',
          content: `Hata: ${response.error || 'Bilinmeyen hata'}`,
        })
      }
    } catch (error) {
      addMessage({
        role: 'assistant',
        content: `Baglanti hatasi: ${error instanceof Error ? error.message : 'Bilinmeyen hata'}`,
      })
    } finally {
      if (!isStreaming) {
        setLoading(false)
      }
    }
  }

  function handleNewChat() {
    reset()
    inputRef.current?.focus()
  }

  async function handleDeleteSession(sessionId: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Bu sohbeti silmek istediginizden emin misiniz?')) return

    try {
      await api.deleteSession(sessionId)
      if (currentSessionId === sessionId) {
        reset()
      }
      loadSessions()
    } catch (error) {
      console.error('Failed to delete session:', error)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
  }

  return (
    <div className="flex h-full">
      {/* Sessions Sidebar */}
      <aside className="w-[280px] flex flex-col border-r" style={{
        background: 'rgb(18, 18, 18)',
        borderColor: 'rgb(50, 50, 50)'
      }}>
        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all"
            style={{
              background: 'rgb(38, 38, 38)',
              color: 'white',
              border: '1px solid rgb(50, 50, 50)'
            }}
          >
            <Plus size={18} />
            Yeni Sohbet
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.length === 0 ? (
            <div className="text-center py-8 text-sm" style={{ color: 'rgb(115, 115, 115)' }}>
              Henuz sohbet yok
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === currentSessionId}
                  onClick={() => setCurrentSessionId(session.id)}
                  onDelete={(e) => handleDeleteSession(session.id, e)}
                />
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-w-0" style={{ background: 'rgb(12, 12, 12)' }}>
        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isStreaming ? (
            <WelcomeScreen onSuggestionClick={setInput} />
          ) : (
            <div className="chat-container py-6">
              {messages.map((message, index) => (
                <MessageRow key={index} message={message} />
              ))}

              {/* Streaming message */}
              {isStreaming && streamingText && (
                <div className="message-row">
                  <div className="message-avatar assistant">C</div>
                  <div className="message-bubble">
                    <div className="message-content">
                      {streamingText}
                      <span className="streaming-cursor" />
                    </div>
                  </div>
                </div>
              )}

              {/* Loading indicator */}
              {isLoading && !isStreaming && (
                <div className="message-row">
                  <div className="message-avatar assistant">C</div>
                  <div className="message-bubble">
                    <div className="typing-indicator">
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4" style={{ background: 'rgb(12, 12, 12)' }}>
          <div className="chat-container">
            <div
              className="flex items-end gap-3 rounded-2xl p-3"
              style={{
                background: 'rgb(26, 26, 26)',
                border: '1px solid rgb(50, 50, 50)'
              }}
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Cortex'e bir soru sor..."
                disabled={isLoading || isStreaming}
                rows={1}
                className="flex-1 bg-transparent resize-none outline-none text-sm"
                style={{
                  minHeight: '24px',
                  maxHeight: '200px',
                  color: 'rgb(236, 236, 236)'
                }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading || isStreaming}
                className="p-2 rounded-lg transition-all disabled:opacity-30"
                style={{
                  background: input.trim() ? '#14b8a6' : 'rgb(50, 50, 50)',
                  color: 'white'
                }}
              >
                <ArrowUp size={18} />
              </button>
            </div>
            <p className="text-xs text-center mt-2" style={{ color: 'rgb(115, 115, 115)' }}>
              Cortex Confluence dokumanlarinizi kullanarak yanitlar uretir
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function SessionItem({
  session,
  isActive,
  onClick,
  onDelete,
}: {
  session: Session
  isActive: boolean
  onClick: () => void
  onDelete: (e: React.MouseEvent) => void
}) {
  return (
    <div
      onClick={onClick}
      className="group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all"
      style={{
        background: isActive ? 'rgba(20, 184, 166, 0.15)' : 'transparent',
        color: isActive ? '#14b8a6' : 'rgb(163, 163, 163)'
      }}
    >
      <MessageSquare size={16} className="shrink-0 opacity-60" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: isActive ? '#14b8a6' : 'rgb(236, 236, 236)' }}>
          {session.title}
        </p>
        <p className="text-xs" style={{ color: 'rgb(115, 115, 115)' }}>
          {formatDate(session.last_message)}
        </p>
      </div>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 p-1 rounded transition-all hover:bg-red-500/20"
      >
        <Trash2 size={14} className="text-red-400" />
      </button>
    </div>
  )
}

function WelcomeScreen({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }) {
  const suggestions = [
    { title: 'Proje Yapisi', desc: 'Kod organizasyonu nasil?' },
    { title: 'API Dokumantasyonu', desc: 'Endpoint\'ler ve kullanim' },
    { title: 'Deployment Sureci', desc: 'Production\'a nasil cikarim?' },
    { title: 'Onboarding', desc: 'Yeni baslayanlar icin rehber' },
  ]

  return (
    <div className="welcome-container">
      <div className="welcome-logo">C</div>
      <h1 className="welcome-title">Cortex</h1>
      <p className="welcome-subtitle">
        Confluence dokumanlariniza AI destekli erisim. Projeler, API'ler ve surecler hakkinda her seyi sorabilirsiniz.
      </p>
      <div className="suggestion-grid">
        {suggestions.map((item) => (
          <button
            key={item.title}
            onClick={() => onSuggestionClick(item.title)}
            className="suggestion-card"
          >
            <div className="suggestion-title">{item.title}</div>
            <div className="suggestion-desc">{item.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageRow({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`message-avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? 'S' : 'C'}
      </div>
      <div className={`message-bubble ${isUser ? 'user' : ''}`}>
        <div className={`message-content ${isUser ? 'user-content' : ''}`}>
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <div className="sources-label">Kaynaklar</div>
            <div>
              {message.sources.map((source, i) => (
                <a
                  key={i}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-chip"
                >
                  <ExternalLink size={12} />
                  {truncate(source.title, 35)}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Stats - Minimal */}
        {!isUser && message.stats && message.stats.duration_ms > 0 && (
          <div className="mt-2 text-xs" style={{ color: 'rgb(115, 115, 115)' }}>
            {(message.stats.duration_ms / 1000).toFixed(1)}s
            {message.stats.tokens?.total > 0 && ` · ${message.stats.tokens.total} token`}
          </div>
        )}
      </div>
    </div>
  )
}
