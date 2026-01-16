import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { MessageSquare, Database, Settings, Menu, X } from 'lucide-react'
import { useStore } from '@/lib/store'

const navItems = [
  { path: '/', label: 'Chat', icon: MessageSquare },
  { path: '/database', label: 'Veritabani', icon: Database },
  { path: '/settings', label: 'Ayarlar', icon: Settings },
]

export function Layout() {
  const location = useLocation()
  const { isSidebarOpen, setSidebarOpen } = useStore()

  const isChat = location.pathname === '/'

  return (
    <div className="flex h-screen" style={{ background: 'rgb(12, 12, 12)' }}>
      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!isSidebarOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg hover:bg-white/5 text-gray-400"
      >
        {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop for mobile */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <nav
        className={`
          fixed lg:relative z-40 h-full transition-transform duration-200 sidebar
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${isChat ? 'w-[260px]' : 'w-[260px] lg:w-[72px]'}
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-4 border-b" style={{ borderColor: 'rgb(50, 50, 50)' }}>
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center font-bold text-white text-lg"
              style={{ background: 'linear-gradient(135deg, #14b8a6, #0d9488)' }}
            >
              C
            </div>
            <span className={`font-semibold text-white ${!isChat ? 'lg:hidden' : ''}`}>
              Cortex
            </span>
          </div>
        </div>

        {/* Nav Items */}
        <div className="flex-1 py-3 px-2">
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive = location.pathname === path
            return (
              <NavLink
                key={path}
                to={path}
                onClick={() => setSidebarOpen(false)}
                className={`sidebar-item mb-1 ${isActive ? 'active' : ''}`}
                title={label}
              >
                <Icon size={20} />
                <span className={!isChat ? 'lg:hidden' : ''}>
                  {label}
                </span>
              </NavLink>
            )
          })}
        </div>

        {/* Footer */}
        <div
          className={`p-4 border-t text-xs ${!isChat ? 'lg:hidden' : ''}`}
          style={{ borderColor: 'rgb(50, 50, 50)', color: 'rgb(115, 115, 115)' }}
        >
          <p className="font-medium text-gray-400">Cortex v2.0</p>
          <p className="mt-0.5">Powered by OpenAI</p>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
