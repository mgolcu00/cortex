import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { ChatPage } from '@/pages/ChatPage'
import { DatabasePage } from '@/pages/DatabasePage'
import { SettingsPage } from '@/pages/SettingsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<ChatPage />} />
        <Route path="database" element={<DatabasePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default App
