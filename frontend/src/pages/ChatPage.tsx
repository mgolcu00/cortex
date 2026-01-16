import { useEffect, useState, useRef } from 'react'
import {
  Plus,
  Trash2,
  MessageSquare,
  ExternalLink,
  ArrowUp,
  ThumbsUp,
  ThumbsDown,
  Clock,
  Sparkles,
  Copy,
  Check,
  Bot,
  User,
  Loader2,
  FileText,
  Lightbulb,
  Code,
  Rocket,
  BookOpen,
  Search,
  Settings,
  Database,
  Zap,
  HelpCircle,
  Users,
  Shield,
  Terminal,
  GitBranch,
  Package,
  Cloud,
  Server,
  Layers,
  Workflow,
  type LucideIcon,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useStore } from '@/lib/store'
import * as api from '@/lib/api'
import { formatDate, generateId, truncate } from '@/lib/utils'
import type { Message, Session, StarterItem } from '@/types'

// Icon mapping for dynamic icons
const iconMap: Record<string, LucideIcon> = {
  Code,
  FileText,
  Rocket,
  Lightbulb,
  BookOpen,
  Search,
  Settings,
  Database,
  Zap,
  MessageSquare,
  HelpCircle,
  Users,
  Shield,
  Terminal,
  GitBranch,
  Package,
  Cloud,
  Server,
  Layers,
  Workflow,
}

const defaultStarters: StarterItem[] = [
  { title: 'Proje Yapisi', description: 'Kod organizasyonu nasil?', icon: 'Code' },
  { title: 'API Dokumantasyonu', description: "Endpoint'ler ve kullanim", icon: 'FileText' },
  { title: 'Deployment Sureci', description: "Production'a nasil cikarim?", icon: 'Rocket' },
  { title: 'Onboarding', description: 'Yeni baslayanlar icin rehber', icon: 'Lightbulb' },
]

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
  const [feedbacks, setFeedbacks] = useState<Record<number, 'like' | 'dislike'>>({})
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [starters, setStarters] = useState<StarterItem[]>(defaultStarters)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const isSendingRef = useRef(false)

  useEffect(() => {
    loadSessions()
    loadStarters()
  }, [])

  async function loadStarters() {
    try {
      const data = await api.getStarters()
      if (data.starters && data.starters.length > 0) {
        setStarters(data.starters)
      }
    } catch (error) {
      console.error('Failed to load starters:', error)
    }
  }

  useEffect(() => {
    if (currentSessionId) {
      if (!isSendingRef.current) {
        loadSessionMessages(currentSessionId)
        loadFeedbacks(currentSessionId)
      }
    } else {
      setMessages([])
      setFeedbacks({})
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

  async function loadFeedbacks(sessionId: string) {
    try {
      const data = await api.getSessionFeedback(sessionId)
      setFeedbacks(data.feedbacks || {})
    } catch (error) {
      console.error('Failed to load feedbacks:', error)
    }
  }

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
    }, 25)
  }

  async function handleSend() {
    if (!input.trim() || isLoading) return

    isSendingRef.current = true

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

        simulateStreaming(response.answer || '', () => {
          addMessage(assistantMessage)
          isSendingRef.current = false
          setLoading(false)
          loadSessions()
        })
      } else {
        addMessage({
          role: 'assistant',
          content: `Hata: ${response.error || 'Bilinmeyen hata'}`,
        })
        isSendingRef.current = false
        setLoading(false)
      }
    } catch (error) {
      addMessage({
        role: 'assistant',
        content: `Baglanti hatasi: ${error instanceof Error ? error.message : 'Bilinmeyen hata'}`,
      })
      isSendingRef.current = false
      setLoading(false)
    }
  }

  function handleNewChat() {
    reset()
    setFeedbacks({})
    inputRef.current?.focus()
  }

  async function handleDeleteSession(sessionId: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Bu sohbeti silmek istediginizden emin misiniz?')) return

    try {
      await api.deleteSession(sessionId)
      if (currentSessionId === sessionId) {
        reset()
        setFeedbacks({})
      }
      loadSessions()
    } catch (error) {
      console.error('Failed to delete session:', error)
    }
  }

  async function handleFeedback(messageIndex: number, feedback: 'like' | 'dislike') {
    if (!currentSessionId) return

    const currentFeedback = feedbacks[messageIndex]

    try {
      if (currentFeedback === feedback) {
        await api.deleteFeedback(currentSessionId, messageIndex)
        setFeedbacks(prev => {
          const next = { ...prev }
          delete next[messageIndex]
          return next
        })
      } else {
        await api.submitFeedback(currentSessionId, messageIndex, feedback)
        setFeedbacks(prev => ({ ...prev, [messageIndex]: feedback }))
      }
    } catch (error) {
      console.error('Failed to submit feedback:', error)
    }
  }

  async function handleCopy(text: string, index: number) {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
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
      <aside className="w-[280px] flex flex-col border-r" style={{
        background: 'rgb(18, 18, 18)',
        borderColor: 'rgb(50, 50, 50)'
      }}>
        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium text-sm transition-all hover:scale-[1.02] active:scale-[0.98]"
            style={{
              background: 'linear-gradient(135deg, #f97316, #ea580c)',
              color: 'white',
              boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3)'
            }}
          >
            <Plus size={18} />
            Yeni Sohbet
          </button>
        </div>

        <div className="px-3 pb-2">
          <div className="flex items-center gap-2 text-[11px] text-gray-500 font-medium uppercase tracking-wider">
            <Clock size={12} />
            <span>Gecmis Sohbetler</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.length === 0 ? (
            <div className="text-center py-8 px-4">
              <MessageSquare size={32} className="mx-auto mb-3 text-gray-600" />
              <p className="text-sm text-gray-500">Henuz sohbet yok</p>
              <p className="text-xs text-gray-600 mt-1">Yeni bir sohbet baslatarak Cortex'e soru sorun</p>
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

      <div className="flex-1 flex flex-col min-w-0" style={{ background: 'rgb(12, 12, 12)' }}>
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isStreaming ? (
            <WelcomeScreen starters={starters} onSuggestionClick={setInput} />
          ) : (
            <div className="chat-container py-6">
              {messages.map((message, index) => (
                <MessageRow
                  key={index}
                  message={message}
                  feedback={feedbacks[index]}
                  onFeedback={(fb) => handleFeedback(index, fb)}
                  onCopy={() => handleCopy(message.content, index)}
                  isCopied={copiedIndex === index}
                />
              ))}

              {isStreaming && streamingText && (
                <div className="message-row">
                  <div className="message-avatar assistant">
                    <Bot size={18} />
                  </div>
                  <div className="message-bubble">
                    <div className="message-content">
                      {streamingText}
                      <span className="streaming-cursor" />
                    </div>
                  </div>
                </div>
              )}

              {isLoading && !isStreaming && (
                <div className="message-row">
                  <div className="message-avatar assistant">
                    <Bot size={18} />
                  </div>
                  <div className="message-bubble">
                    <div className="flex items-center gap-3 text-gray-400">
                      <Loader2 size={16} className="animate-spin" />
                      <span className="text-sm">Dusunuyor...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

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
                className="p-2.5 rounded-xl transition-all disabled:opacity-30 hover:scale-105 active:scale-95"
                style={{
                  background: input.trim() ? 'linear-gradient(135deg, #f97316, #ea580c)' : 'rgb(50, 50, 50)',
                  color: 'white',
                  boxShadow: input.trim() ? '0 4px 12px rgba(249, 115, 22, 0.3)' : 'none'
                }}
              >
                <ArrowUp size={18} />
              </button>
            </div>
            <p className="text-xs text-center mt-2 flex items-center justify-center gap-1" style={{ color: 'rgb(115, 115, 115)' }}>
              <Sparkles size={12} className="text-orange-500" />
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
      className="group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all"
      style={{
        background: isActive ? 'rgba(249, 115, 22, 0.15)' : 'transparent',
        color: isActive ? '#f97316' : 'rgb(163, 163, 163)'
      }}
    >
      <MessageSquare size={16} className="shrink-0 opacity-60" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: isActive ? '#f97316' : 'rgb(236, 236, 236)' }}>
          {session.title}
        </p>
        <p className="text-xs" style={{ color: 'rgb(115, 115, 115)' }}>
          {formatDate(session.last_message)}
        </p>
      </div>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all hover:bg-red-500/20"
      >
        <Trash2 size={14} className="text-red-400" />
      </button>
    </div>
  )
}

function WelcomeScreen({
  starters,
  onSuggestionClick,
}: {
  starters: StarterItem[]
  onSuggestionClick: (text: string) => void
}) {
  return (
    <div className="welcome-container">
      <div className="welcome-logo">
        <Sparkles size={32} />
      </div>
      <h1 className="welcome-title">Cortex</h1>
      <p className="welcome-subtitle">
        Confluence dokumanlariniza AI destekli erisim. Projeler, API'ler ve surecler hakkinda her seyi sorabilirsiniz.
      </p>
      <div className="suggestion-grid">
        {starters.map((item) => {
          const IconComponent = iconMap[item.icon] || Lightbulb
          return (
            <button
              key={item.title}
              onClick={() => onSuggestionClick(item.description)}
              className="suggestion-card group"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-orange-500/10 text-orange-400 group-hover:bg-orange-500/20 transition-colors">
                  <IconComponent size={16} />
                </div>
                <div className="suggestion-title">{item.title}</div>
              </div>
              <div className="suggestion-desc">{item.description}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function MessageRow({
  message,
  feedback,
  onFeedback,
  onCopy,
  isCopied,
}: {
  message: Message
  feedback?: 'like' | 'dislike'
  onFeedback: (feedback: 'like' | 'dislike') => void
  onCopy: () => void
  isCopied: boolean
}) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`message-avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className={`message-bubble ${isUser ? 'user' : ''}`}>
        <div className={`message-content ${isUser ? 'user-content' : ''}`}>
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <div className="sources-label">
              <FileText size={10} className="inline mr-1" />
              Kaynaklar
            </div>
            <div className="flex flex-wrap">
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

        {!isUser && (
          <div className="flex items-center justify-between mt-3 pt-2 border-t" style={{ borderColor: 'rgb(50, 50, 50)' }}>
            <div className="flex items-center gap-1">
              <button
                onClick={() => onFeedback('like')}
                className={`feedback-btn ${feedback === 'like' ? 'active like' : ''}`}
                title="Begendim"
              >
                <ThumbsUp size={14} />
              </button>
              <button
                onClick={() => onFeedback('dislike')}
                className={`feedback-btn ${feedback === 'dislike' ? 'active dislike' : ''}`}
                title="Begenmedim"
              >
                <ThumbsDown size={14} />
              </button>
              <div className="w-px h-4 mx-1" style={{ background: 'rgb(50, 50, 50)' }} />
              <button
                onClick={onCopy}
                className="feedback-btn"
                title="Kopyala"
              >
                {isCopied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
              </button>
            </div>

            {message.stats && message.stats.duration_ms > 0 && (
              <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(115, 115, 115)' }}>
                <Clock size={12} />
                <span>{(message.stats.duration_ms / 1000).toFixed(1)}s</span>
                {message.stats.tokens?.total > 0 && (
                  <>
                    <span>•</span>
                    <span>{message.stats.tokens.total} token</span>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
