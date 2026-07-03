import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/app-shell'
import { ThemeProvider } from '@/components/theme-provider'
import Dashboard from '@/pages/Dashboard'
import Repositories from '@/pages/Repositories'
import Settings from '@/pages/Settings'
import SubmitWorkflow from '@/pages/SubmitWorkflow'
import TaskDetail from '@/pages/TaskDetail'
import TaskList from '@/pages/TaskList'

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/submit" element={<SubmitWorkflow />} />
            <Route path="/tasks" element={<TaskList />} />
            <Route path="/tasks/:taskUuid" element={<TaskDetail />} />
            <Route path="/repositories" element={<Repositories />} />
            <Route path="/index" element={<Navigate to="/repositories" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ThemeProvider>
  )
}
