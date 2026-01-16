import { useEffect, useState } from 'react'
import { Search, ChevronLeft, ChevronRight, FileText, Layers, X, ExternalLink, RefreshCw, Database } from 'lucide-react'
import * as api from '@/lib/api'
import { formatDate, formatNumber } from '@/lib/utils'
import type { Page, PageDetail, Space, Stats } from '@/types'

export function DatabasePage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [spaces, setSpaces] = useState<Space[]>([])
  const [pages, setPages] = useState<Page[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [selectedSpace, setSelectedSpace] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPage, setSelectedPage] = useState<PageDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSyncing, setIsSyncing] = useState(false)

  const limit = 25

  useEffect(() => {
    loadStats()
    loadSpaces()
  }, [])

  useEffect(() => {
    loadPages()
  }, [offset, selectedSpace, searchQuery])

  async function loadStats() {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  async function loadSpaces() {
    try {
      const data = await api.getSpaces()
      setSpaces(data.spaces)
    } catch (error) {
      console.error('Failed to load spaces:', error)
    }
  }

  async function loadPages() {
    setIsLoading(true)
    try {
      const data = await api.getPages({
        limit,
        offset,
        space: selectedSpace || undefined,
        search: searchQuery || undefined,
      })
      setPages(data.pages)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to load pages:', error)
    } finally {
      setIsLoading(false)
    }
  }

  async function handlePageClick(pageId: string) {
    try {
      const detail = await api.getPageDetail(pageId)
      setSelectedPage(detail)
    } catch (error) {
      console.error('Failed to load page detail:', error)
    }
  }

  async function handleSync() {
    if (!confirm('Confluence sync baslatilsin mi? Bu islem birkac dakika surebilir.')) return

    setIsSyncing(true)
    try {
      await api.runSync('full')
      setTimeout(() => {
        loadStats()
        loadPages()
        setIsSyncing(false)
      }, 5000)
    } catch (error) {
      console.error('Failed to start sync:', error)
      setIsSyncing(false)
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setOffset(0)
    loadPages()
  }

  return (
    <div className="h-full flex flex-col" style={{ background: 'rgb(12, 12, 12)' }}>
      <header
        className="h-14 flex items-center justify-between px-6 border-b"
        style={{ background: 'rgb(18, 18, 18)', borderColor: 'rgb(50, 50, 50)' }}
      >
        <div className="flex items-center gap-3">
          <Database size={20} className="text-orange-500" />
          <h1 className="text-lg font-semibold text-white">Veritabani</h1>
        </div>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="btn btn-secondary btn-sm"
        >
          <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} />
          {isSyncing ? 'Syncleniyor...' : 'Sync Baslat'}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Toplam Sayfa"
            value={formatNumber(stats?.database.pages || 0)}
            icon={<FileText size={18} />}
          />
          <StatCard
            label="Toplam Chunk"
            value={formatNumber(stats?.database.chunks || 0)}
            icon={<Layers size={18} />}
          />
          <StatCard
            label="Son Sync"
            value={formatDate(stats?.database.last_sync || null)}
            status={stats?.database.last_sync_success}
          />
          <StatCard
            label="Toplam Istek"
            value={formatNumber(stats?.usage.total_requests || 0)}
            subtext={`${formatNumber(stats?.usage.total_tokens || 0)} token`}
          />
        </div>

        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={selectedSpace}
            onChange={(e) => {
              setSelectedSpace(e.target.value)
              setOffset(0)
            }}
            className="input w-48"
          >
            <option value="">Tum Space'ler</option>
            {spaces.map((space) => (
              <option key={space.space_key} value={space.space_key}>
                {space.space_key} ({space.page_count})
              </option>
            ))}
          </select>

          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                placeholder="Sayfa ara..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-9 w-64"
              />
            </div>
          </form>
        </div>

        <div className="card overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Sayfa</th>
                <th>Space</th>
                <th>Chunks</th>
                <th>Version</th>
                <th>Guncelleme</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="text-center py-8" style={{ color: 'rgb(115, 115, 115)' }}>
                    Yukleniyor...
                  </td>
                </tr>
              ) : pages.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8" style={{ color: 'rgb(115, 115, 115)' }}>
                    Sayfa bulunamadi
                  </td>
                </tr>
              ) : (
                pages.map((page) => (
                  <tr
                    key={page.page_id}
                    onClick={() => handlePageClick(page.page_id)}
                    className="cursor-pointer"
                  >
                    <td>
                      <p className="font-medium truncate max-w-xs text-white">{page.title}</p>
                      <p className="text-xs" style={{ color: 'rgb(115, 115, 115)' }}>ID: {page.page_id}</p>
                    </td>
                    <td>
                      <span className="badge badge-primary">{page.space_key}</span>
                    </td>
                    <td>
                      <span className="badge badge-success">{page.chunk_count} chunk</span>
                    </td>
                    <td style={{ color: 'rgb(163, 163, 163)' }}>v{page.version}</td>
                    <td className="text-sm" style={{ color: 'rgb(163, 163, 163)' }}>
                      {formatDate(page.updated_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          <div
            className="flex items-center justify-between p-4 border-t"
            style={{ borderColor: 'rgb(50, 50, 50)' }}
          >
            <span className="text-sm" style={{ color: 'rgb(115, 115, 115)' }}>
              {offset + 1}-{Math.min(offset + limit, total)} / {total} sayfa
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="btn btn-ghost btn-sm"
              >
                <ChevronLeft size={16} />
                Onceki
              </button>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
                className="btn btn-ghost btn-sm"
              >
                Sonraki
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {selectedPage && (
        <PageDetailModal
          page={selectedPage}
          onClose={() => setSelectedPage(null)}
        />
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  subtext,
  status,
}: {
  label: string
  value: string
  icon?: React.ReactNode
  subtext?: string
  status?: boolean | null
}) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between mb-2">
        <span className="stat-label">{label}</span>
        {icon && <span className="text-orange-500">{icon}</span>}
      </div>
      <p className="stat-value">{value}</p>
      {subtext && <p className="stat-subtext">{subtext}</p>}
      {status !== undefined && status !== null && (
        <p className={`stat-subtext ${status ? 'text-green-400' : 'text-red-400'}`}>
          {status ? 'Basarili' : 'Basarisiz'}
        </p>
      )}
    </div>
  )
}

function PageDetailModal({
  page,
  onClose,
}: {
  page: PageDetail
  onClose: () => void
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content max-w-3xl" onClick={(e) => e.stopPropagation()}>
        <div
          className="flex items-center justify-between p-4 border-b"
          style={{ borderColor: 'rgb(50, 50, 50)' }}
        >
          <h2 className="text-lg font-semibold text-white truncate pr-4">{page.title}</h2>
          <button onClick={onClose} className="btn btn-ghost p-1">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4" style={{ maxHeight: 'calc(80vh - 80px)' }}>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="stat-label">Space</p>
              <p className="font-medium text-white">{page.space_key}</p>
            </div>
            <div>
              <p className="stat-label">Version</p>
              <p className="font-medium text-white">v{page.version}</p>
            </div>
            <div>
              <p className="stat-label">Guncelleme</p>
              <p className="font-medium text-white">{formatDate(page.updated_at)}</p>
            </div>
          </div>

          <div className="mb-4">
            <p className="stat-label">URL</p>
            <a
              href={page.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-orange-400 hover:underline inline-flex items-center gap-1"
            >
              {page.url}
              <ExternalLink size={12} />
            </a>
          </div>

          <div className="mb-4">
            <p className="stat-label">Icerik (onizleme)</p>
            <div
              className="rounded-lg p-3 text-sm font-mono whitespace-pre-wrap max-h-48 overflow-y-auto"
              style={{ background: 'rgb(26, 26, 26)', color: 'rgb(163, 163, 163)' }}
            >
              {page.body_text || '(Bos)'}
            </div>
          </div>

          <div>
            <p className="stat-label mb-2">Chunks ({page.chunks.length})</p>
            <div className="space-y-2">
              {page.chunks.map((chunk) => (
                <div
                  key={chunk.chunk_id}
                  className="rounded-lg p-3"
                  style={{ background: 'rgb(26, 26, 26)' }}
                >
                  <div
                    className="flex items-center justify-between mb-2 text-xs"
                    style={{ color: 'rgb(115, 115, 115)' }}
                  >
                    <span>
                      #{chunk.chunk_index}
                      {chunk.heading_path && ` - ${chunk.heading_path}`}
                    </span>
                    <span>{chunk.token_count || '-'} token</span>
                  </div>
                  <p className="text-sm" style={{ color: 'rgb(163, 163, 163)' }}>{chunk.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
