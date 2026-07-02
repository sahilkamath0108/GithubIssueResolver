import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { checkHealth } from './api/client'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import IndexRepo from './pages/IndexRepo'
import Settings from './pages/Settings'
import SubmitWorkflow from './pages/SubmitWorkflow'
import TaskDetail from './pages/TaskDetail'
import TaskList from './pages/TaskList'

function AppShell() {
  const [healthOk, setHealthOk] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        await checkHealth()
        if (!cancelled) setHealthOk(true)
      } catch {
        if (!cancelled) setHealthOk(false)
      }
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <Layout healthOk={healthOk}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/submit" element={<SubmitWorkflow />} />
        <Route path="/tasks" element={<TaskList />} />
        <Route path="/tasks/:taskUuid" element={<TaskDetail />} />
        <Route path="/index" element={<IndexRepo />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
