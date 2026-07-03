import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/app-shell'
import { RequireAuth } from '@/components/require-auth'
import { ThemeProvider } from '@/components/theme-provider'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/Login'
import Repositories from '@/pages/Repositories'
import Settings from '@/pages/Settings'
import SubmitWorkflow from '@/pages/SubmitWorkflow'
import TaskDetail from '@/pages/TaskDetail'
import TaskList from '@/pages/TaskList'

function Protected({ children }) {
  return <RequireAuth>{children}</RequireAuth>
}

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Protected><Dashboard /></Protected>} />
            <Route path="/submit" element={<Protected><SubmitWorkflow /></Protected>} />
            <Route path="/tasks" element={<Protected><TaskList /></Protected>} />
            <Route path="/tasks/:taskUuid" element={<Protected><TaskDetail /></Protected>} />
            <Route path="/repositories" element={<Protected><Repositories /></Protected>} />
            <Route path="/index" element={<Navigate to="/repositories" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ThemeProvider>
  )
}
