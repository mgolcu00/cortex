import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Session, Message, Stats, HealthStatus } from '@/types'

interface AppState {
  // Session state
  currentSessionId: string | null
  sessions: Session[]
  messages: Message[]

  // UI state
  isSidebarOpen: boolean
  isLoading: boolean

  // Health & Stats
  health: HealthStatus | null
  stats: Stats | null

  // Actions
  setCurrentSessionId: (id: string | null) => void
  setSessions: (sessions: Session[]) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setSidebarOpen: (open: boolean) => void
  setHealth: (health: HealthStatus | null) => void
  setStats: (stats: Stats | null) => void
  reset: () => void
}

const initialState = {
  currentSessionId: null,
  sessions: [],
  messages: [],
  isSidebarOpen: true,
  isLoading: false,
  health: null,
  stats: null,
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialState,

      setCurrentSessionId: (id) => set({ currentSessionId: id }),
      setSessions: (sessions) => set({ sessions }),
      setMessages: (messages) => set({ messages }),
      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),
      setLoading: (loading) => set({ isLoading: loading }),
      setSidebarOpen: (open) => set({ isSidebarOpen: open }),
      setHealth: (health) => set({ health }),
      setStats: (stats) => set({ stats }),
      reset: () =>
        set({
          currentSessionId: null,
          messages: [],
        }),
    }),
    {
      name: 'cortex-storage',
      partialize: (state) => ({
        currentSessionId: state.currentSessionId,
        isSidebarOpen: state.isSidebarOpen,
      }),
    }
  )
)
