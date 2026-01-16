import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  MessageSquare,
  Database,
  Settings,
  Menu,
  X,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Zap,
  BookOpen,
  Search,
  LayoutDashboard,
  Github,
  Heart,
} from 'lucide-react'
import { useStore } from '@/lib/store'
import { useState, useEffect } from 'react'

const navItems = [
  { path: '/', label: 'Chat', icon: MessageSquare, description: 'AI ile sohbet' },
  { path: '/database', label: 'Veritabani', icon: Database, description: 'Indeksli sayfalar' },
  { path: '/settings', label: 'Ayarlar', icon: Settings, description: 'Konfigurasyon' },
]

export function Layout() {
  const location = useLocation()
  const { isSidebarOpen, setSidebarOpen } = useStore()

  const isChat = location.pathname === '/'

  const [isExpanded, setIsExpanded] = useState(isChat)

  useEffect(() => {
    setIsExpanded(isChat)
  }, [isChat])

  return (
    <div className="flex h-screen" style={{ background: 'rgb(12, 12, 12)' }}>
      <button
        onClick={() => setSidebarOpen(!isSidebarOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg hover:bg-white/5 text-gray-400"
      >
        {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <nav
        className={`
          fixed lg:relative z-40 h-full transition-all duration-300 sidebar
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${isExpanded ? 'w-[260px]' : 'w-[72px]'}
        `}
      >
        <div className="h-16 flex items-center justify-between px-4 border-b" style={{ borderColor: 'rgb(50, 50, 50)' }}>
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-white text-lg shadow-lg"
              style={{ background: 'linear-gradient(135deg, #f97316, #ea580c)' }}
            >
              <Sparkles size={20} />
            </div>
            {isExpanded && (
              <div className="flex flex-col">
                <span className="font-bold text-white text-lg tracking-tight">Cortex</span>
                <span className="text-[10px] text-gray-500 -mt-0.5">AI Knowledge Assistant</span>
              </div>
            )}
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="hidden lg:flex p-1.5 rounded-lg hover:bg-white/5 text-gray-500 hover:text-gray-300 transition-colors"
          >
            {isExpanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {isExpanded && (
          <div className="px-3 py-3 border-b" style={{ borderColor: 'rgb(50, 50, 50)' }}>
            <div className="flex items-center gap-2 text-[11px] text-gray-500">
              <Zap size={12} className="text-orange-500" />
              <span>Powered by GPT-5 + pgvector</span>
            </div>
          </div>
        )}

        <div className="flex-1 py-3 px-2 space-y-1">
          {navItems.map(({ path, label, icon: Icon, description }) => {
            const isActive = location.pathname === path
            return (
              <NavLink
                key={path}
                to={path}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200
                  ${isActive
                    ? 'bg-orange-500/15 text-orange-400'
                    : 'text-gray-400 hover:bg-white/5 hover:text-white'
                  }
                  ${!isExpanded ? 'justify-center' : ''}
                `}
                title={!isExpanded ? label : undefined}
              >
                <Icon size={20} className={isActive ? 'text-orange-400' : ''} />
                {isExpanded && (
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{label}</span>
                    <span className="text-[10px] text-gray-500">{description}</span>
                  </div>
                )}
              </NavLink>
            )
          })}
        </div>

        {isExpanded && (
          <div className="px-3 pb-3">
            <div
              className="p-3 rounded-xl text-xs"
              style={{ background: 'rgba(249, 115, 22, 0.08)', border: '1px solid rgba(249, 115, 22, 0.15)' }}
            >
              <div className="flex items-center gap-2 text-orange-400 font-medium mb-2">
                <BookOpen size={14} />
                <span>Ozellikler</span>
              </div>
              <div className="space-y-1 text-gray-400">
                <div className="flex items-center gap-2">
                  <Search size={10} />
                  <span>Semantik arama</span>
                </div>
                <div className="flex items-center gap-2">
                  <LayoutDashboard size={10} />
                  <span>Akilli chunking</span>
                </div>
                <div className="flex items-center gap-2">
                  <Zap size={10} />
                  <span>Gercek zamanli sync</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div
          className={`p-4 border-t ${!isExpanded ? 'flex justify-center' : ''}`}
          style={{ borderColor: 'rgb(50, 50, 50)' }}
        >
          {isExpanded ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Heart size={12} className="text-red-400" />
                <span>
                  Made by{' '}
                  <a
                    href="https://github.com/mgolcu00"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-orange-400 hover:text-orange-300 transition-colors font-medium"
                  >
                    Mert Golcu
                  </a>
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-gray-600">
                <span>Cortex v2.0</span>
                <span>•</span>
                <a
                  href="https://github.com/mgolcu00/cortex"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-gray-400 transition-colors"
                >
                  <Github size={12} />
                </a>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Heart size={14} className="text-red-400" />
            </div>
          )}
        </div>
      </nav>

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
