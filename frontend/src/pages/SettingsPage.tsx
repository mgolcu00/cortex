import { useEffect, useState } from 'react'
import {
  Save,
  RotateCcw,
  RefreshCw,
  Check,
  AlertCircle,
  Play,
  Settings,
  Zap,
  Cloud,
  Database,
  CheckCircle2,
  XCircle,
  Plus,
  Trash2,
  GripVertical,
} from 'lucide-react'
import * as api from '@/lib/api'
import type { AppConfig } from '@/lib/api'
import { formatNumber, formatCurrency, formatDate } from '@/lib/utils'
import type { Stats, Instructions, Session, StarterItem } from '@/types'

const availableIcons = [
  'Code', 'FileText', 'Rocket', 'Lightbulb', 'BookOpen', 'Search',
  'Settings', 'Database', 'Zap', 'MessageSquare', 'HelpCircle', 'Users',
  'Shield', 'Terminal', 'GitBranch', 'Package', 'Cloud', 'Server', 'Layers', 'Workflow'
]

export function SettingsPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [instructions, setInstructions] = useState<Instructions | null>(null)
  const [editedInstructions, setEditedInstructions] = useState('')
  const [starters, setStarters] = useState<StarterItem[]>([])
  const [isStartersDefault, setIsStartersDefault] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isSavingStarters, setIsSavingStarters] = useState(false)
  const [isResettingStarters, setIsResettingStarters] = useState(false)
  const [syncMode, setSyncMode] = useState<'incremental' | 'full'>('incremental')
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadStats, 10000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    await Promise.all([loadStats(), loadConfig(), loadInstructions(), loadSessions(), loadStarters()])
  }

  async function loadStats() {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  async function loadConfig() {
    try {
      const data = await api.getConfig()
      setConfig(data)
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  async function loadSessions() {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }

  async function loadInstructions() {
    try {
      const data = await api.getInstructions()
      setInstructions(data)
      setEditedInstructions(data.current)
    } catch (error) {
      console.error('Failed to load instructions:', error)
    }
  }

  async function loadStarters() {
    try {
      const data = await api.getStarters()
      setStarters(data.starters)
      setIsStartersDefault(data.is_default)
    } catch (error) {
      console.error('Failed to load starters:', error)
    }
  }

  async function handleSave() {
    if (!editedInstructions.trim()) {
      showToast('error', 'Instructions bos olamaz')
      return
    }

    setIsSaving(true)
    try {
      await api.updateInstructions(editedInstructions)
      await loadInstructions()
      showToast('success', 'Instructions kaydedildi')
    } catch (error) {
      showToast('error', 'Kaydetme hatasi')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleReset() {
    if (!confirm('Instructions varsayilana donduruluecek. Emin misiniz?')) return

    setIsResetting(true)
    try {
      await api.resetInstructions()
      await loadInstructions()
      showToast('success', 'Varsayilana donduruldu')
    } catch (error) {
      showToast('error', 'Reset hatasi')
    } finally {
      setIsResetting(false)
    }
  }

  async function handleSaveStarters() {
    if (starters.length === 0) {
      showToast('error', 'En az bir konu baslatici olmali')
      return
    }

    setIsSavingStarters(true)
    try {
      await api.updateStarters(starters)
      await loadStarters()
      showToast('success', 'Konu baslaticilar kaydedildi')
    } catch (error) {
      showToast('error', 'Kaydetme hatasi')
    } finally {
      setIsSavingStarters(false)
    }
  }

  async function handleResetStarters() {
    if (!confirm('Konu baslaticilar varsayilana donduruluecek. Emin misiniz?')) return

    setIsResettingStarters(true)
    try {
      await api.resetStarters()
      await loadStarters()
      showToast('success', 'Varsayilana donduruldu')
    } catch (error) {
      showToast('error', 'Reset hatasi')
    } finally {
      setIsResettingStarters(false)
    }
  }

  function handleAddStarter() {
    setStarters([...starters, { title: '', description: '', icon: 'Lightbulb' }])
  }

  function handleRemoveStarter(index: number) {
    setStarters(starters.filter((_, i) => i !== index))
  }

  function handleUpdateStarter(index: number, field: keyof StarterItem, value: string) {
    const updated = [...starters]
    updated[index] = { ...updated[index], [field]: value }
    setStarters(updated)
  }

  async function handleSync() {
    setIsSyncing(true)
    try {
      await api.runSync(syncMode)
      showToast('success', `${syncMode === 'full' ? 'Tam' : 'Artimsal'} sync basladi`)
    } catch (error) {
      showToast('error', 'Sync baslatilamadi')
    } finally {
      setIsSyncing(false)
    }
  }

  function showToast(type: 'success' | 'error', message: string) {
    setToast({ type, message })
    setTimeout(() => setToast(null), 3000)
  }

  const hasChanges = editedInstructions !== instructions?.current

  return (
    <div className="h-full flex flex-col" style={{ background: 'rgb(12, 12, 12)' }}>
      <header
        className="h-14 flex items-center px-6 border-b"
        style={{ background: 'rgb(18, 18, 18)', borderColor: 'rgb(50, 50, 50)' }}
      >
        <div className="flex items-center gap-3">
          <Settings size={20} className="text-orange-500" />
          <h1 className="text-lg font-semibold text-white">Ayarlar</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <Section title="Konfigurasyon">
            <p className="text-sm mb-4" style={{ color: 'rgb(115, 115, 115)' }}>
              Bu ayarlar <code className="px-1.5 py-0.5 rounded text-xs" style={{ background: 'rgb(38, 38, 38)' }}>.env</code> dosyasindan
              okunmaktadir. Degistirmek icin dosyayi duzenleyin ve uygulamayi yeniden baslatin.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ConfigCard
                title="OpenAI"
                icon={<Zap size={16} className="text-green-400" />}
                items={[
                  { label: 'Chat Model', value: config?.openai.chat_model || '-' },
                  { label: 'Embedding Model', value: config?.openai.embedding_model || '-' },
                  {
                    label: 'API Key',
                    value: config?.openai.api_key_set ? 'Ayarli' : 'Eksik',
                    status: config?.openai.api_key_set ? 'success' : 'error'
                  },
                ]}
              />

              <ConfigCard
                title="Confluence"
                icon={<Cloud size={16} className="text-blue-400" />}
                items={[
                  { label: 'Base URL', value: config?.confluence.base_url || '-', truncate: true },
                  { label: 'Email', value: config?.confluence.email || '-' },
                  {
                    label: 'API Token',
                    value: config?.confluence.api_token_set ? 'Ayarli' : 'Eksik',
                    status: config?.confluence.api_token_set ? 'success' : 'error'
                  },
                ]}
              />

              <ConfigCard
                title="Veritabani"
                icon={<Database size={16} className="text-purple-400" />}
                items={[
                  { label: 'Host', value: config?.database.url_preview || '-' },
                  {
                    label: 'Baglanti',
                    value: config?.database.url_set ? 'Ayarli' : 'Eksik',
                    status: config?.database.url_set ? 'success' : 'error'
                  },
                ]}
              />

              <ConfigCard
                title="Sync & Arama"
                icon={<RefreshCw size={16} className="text-yellow-400" />}
                items={[
                  { label: 'Sync Araligi', value: `${config?.sync.interval_minutes || 60} dakika` },
                  { label: 'Arama Top-K', value: config?.search.top_k?.toString() || '30' },
                  { label: 'Log Level', value: config?.log_level || 'INFO' },
                ]}
              />
            </div>
          </Section>

          <Section title="Confluence Sync">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="stat-card">
                <p className="stat-label">Durum</p>
                <p className={`stat-value text-base ${stats?.database.last_sync_success ? 'text-green-400' : 'text-yellow-400'}`}>
                  {stats?.database.last_sync_success ? 'Basarili' : 'Bekliyor'}
                </p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Son Sync</p>
                <p className="stat-value text-base">{formatDate(stats?.database.last_sync || null)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Toplam Sayfa</p>
                <p className="stat-value text-base">{formatNumber(stats?.database.pages || 0)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Toplam Chunk</p>
                <p className="stat-value text-base">{formatNumber(stats?.database.chunks || 0)}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <select
                value={syncMode}
                onChange={(e) => setSyncMode(e.target.value as 'incremental' | 'full')}
                className="input w-64"
              >
                <option value="incremental">Artimsal Sync (Yeni/Degisen)</option>
                <option value="full">Tam Sync (Tum Sayfalar)</option>
              </select>
              <button
                onClick={handleSync}
                disabled={isSyncing}
                className="btn btn-primary"
              >
                {isSyncing ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Play size={16} />
                )}
                Sync Baslat
              </button>
            </div>
          </Section>

          <Section title="Kullanim Istatistikleri">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="stat-card">
                <p className="stat-label">Toplam Istek</p>
                <p className="stat-value">{formatNumber(stats?.usage.total_requests || 0)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Toplam Token</p>
                <p className="stat-value">{formatNumber(stats?.usage.total_tokens || 0)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Toplam Maliyet</p>
                <p className="stat-value">{formatCurrency(stats?.usage.total_cost_usd || 0)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Confluence API</p>
                <p className="stat-value">{formatNumber(stats?.usage.total_confluence_requests || 0)}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Aktif Session</p>
                <p className="stat-value">{sessions.length}</p>
              </div>
            </div>
          </Section>

          <Section
            title="Konu Baslaticilar"
            badge={
              isStartersDefault ? (
                <span className="badge badge-success">Varsayilan</span>
              ) : (
                <span className="badge badge-warning">Ozellesmis</span>
              )
            }
          >
            <div
              className="p-4 rounded-lg mb-4"
              style={{ background: 'rgba(249, 115, 22, 0.1)', border: '1px solid rgba(249, 115, 22, 0.2)' }}
            >
              <p className="text-sm" style={{ color: 'rgb(163, 163, 163)' }}>
                <strong className="text-white">Konu Baslaticilar nedir?</strong> Chat ekraninda bos sayfa acildiginda
                kullaniciya gosterilen oneri kartlaridir. Kullanicilar bunlara tiklayarak hizlica soru sorabilir.
              </p>
            </div>

            <div className="space-y-3">
              {starters.map((starter, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 rounded-lg"
                  style={{ background: 'rgb(26, 26, 26)', border: '1px solid rgb(50, 50, 50)' }}
                >
                  <div className="flex items-center justify-center w-8 h-8 mt-1 text-gray-500">
                    <GripVertical size={16} />
                  </div>

                  <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Baslik</label>
                      <input
                        type="text"
                        value={starter.title}
                        onChange={(e) => handleUpdateStarter(index, 'title', e.target.value)}
                        placeholder="Ornek: API Dokumantasyonu"
                        className="input text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Aciklama</label>
                      <input
                        type="text"
                        value={starter.description}
                        onChange={(e) => handleUpdateStarter(index, 'description', e.target.value)}
                        placeholder="Ornek: Endpoint'ler ve kullanim"
                        className="input text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Icon</label>
                      <select
                        value={starter.icon}
                        onChange={(e) => handleUpdateStarter(index, 'icon', e.target.value)}
                        className="input text-sm"
                      >
                        {availableIcons.map((icon) => (
                          <option key={icon} value={icon}>{icon}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <button
                    onClick={() => handleRemoveStarter(index)}
                    className="p-2 rounded-lg hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors mt-5"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}

              <button
                onClick={handleAddStarter}
                className="w-full flex items-center justify-center gap-2 p-3 rounded-lg border-2 border-dashed text-gray-500 hover:text-orange-400 hover:border-orange-500/50 transition-colors"
                style={{ borderColor: 'rgb(50, 50, 50)' }}
              >
                <Plus size={18} />
                Yeni Konu Baslatici Ekle
              </button>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleSaveStarters}
                disabled={isSavingStarters}
                className="btn btn-primary"
              >
                {isSavingStarters ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                Kaydet
              </button>
              <button
                onClick={handleResetStarters}
                disabled={isResettingStarters || isStartersDefault}
                className="btn btn-secondary"
              >
                {isResettingStarters ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <RotateCcw size={16} />
                )}
                Varsayilana Don
              </button>
            </div>
          </Section>

          <Section
            title="Agent Instructions"
            badge={
              instructions?.is_default ? (
                <span className="badge badge-success">Varsayilan</span>
              ) : (
                <span className="badge badge-warning">Ozellesmis</span>
              )
            }
          >
            <div
              className="p-4 rounded-lg mb-4"
              style={{ background: 'rgba(249, 115, 22, 0.1)', border: '1px solid rgba(249, 115, 22, 0.2)' }}
            >
              <p className="text-sm" style={{ color: 'rgb(163, 163, 163)' }}>
                <strong className="text-white">Instructions nedir?</strong> Agent'in nasil davranacagini,
                ne zaman arama yapacagini ve cevaplari nasil formatlayacagini belirleyen sistem prompt'udur.
              </p>
            </div>

            <div className="space-y-3">
              <label className="stat-label">System Prompt</label>
              <textarea
                value={editedInstructions}
                onChange={(e) => setEditedInstructions(e.target.value)}
                className="input font-mono text-sm"
                style={{ height: '400px', resize: 'vertical' }}
                placeholder="Instructions..."
              />
              <p className="text-xs" style={{ color: 'rgb(115, 115, 115)' }}>
                Markdown formatinda yazabilirsiniz. Degisiklikler kaydedilene kadar uygulanmaz.
              </p>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleSave}
                disabled={isSaving || !hasChanges}
                className="btn btn-primary"
              >
                {isSaving ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                Kaydet
              </button>
              <button
                onClick={handleReset}
                disabled={isResetting || instructions?.is_default}
                className="btn btn-secondary"
              >
                {isResetting ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <RotateCcw size={16} />
                )}
                Varsayilana Don
              </button>
            </div>
          </Section>
        </div>
      </div>

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.type === 'success' ? (
            <Check size={18} className="text-green-400" />
          ) : (
            <AlertCircle size={18} className="text-red-400" />
          )}
          <span className="text-white">{toast.message}</span>
        </div>
      )}
    </div>
  )
}

function Section({
  title,
  badge,
  children,
}: {
  title: string
  badge?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="card">
      <div
        className="flex items-center justify-between p-4 border-b"
        style={{ borderColor: 'rgb(50, 50, 50)' }}
      >
        <h2 className="font-semibold text-white">{title}</h2>
        {badge}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

function ConfigCard({
  title,
  icon,
  items,
}: {
  title: string
  icon: React.ReactNode
  items: Array<{
    label: string
    value: string
    status?: 'success' | 'error'
    truncate?: boolean
  }>
}) {
  return (
    <div className="config-card">
      <div className="config-header">
        {icon}
        <span>{title}</span>
      </div>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="config-row">
            <span className="config-label">{item.label}</span>
            <span
              className={`config-value flex items-center gap-1 ${item.status || ''} ${item.truncate ? 'max-w-[140px] truncate' : ''}`}
            >
              {item.status === 'success' && <CheckCircle2 size={14} />}
              {item.status === 'error' && <XCircle size={14} />}
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
