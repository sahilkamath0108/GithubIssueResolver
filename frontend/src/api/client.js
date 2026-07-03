import axios from 'axios'
import { useSettingsStore } from '../store/settings'

function resolveBaseUrl() {
  const stored = useSettingsStore.getState().apiBaseUrl?.trim()
  if (stored) return stored.replace(/\/$/, '')
  return import.meta.env.VITE_API_URL?.replace(/\/$/, '') || ''
}

export const api = axios.create({
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  config.baseURL = resolveBaseUrl()
  const key = useSettingsStore.getState().apiKey?.trim()
  if (key) config.headers['X-API-Key'] = key
  return config
})

export async function fetchAuthStatus() {
  const { useAuthStore } = await import('../store/auth')
  try {
    const { data } = await api.get('/api/v1/auth/status')
    if (data.authenticated) {
      const me = await api.get('/api/v1/auth/me')
      useAuthStore.getState().setAuthStatus(data.oauth_enabled, me.data)
    } else {
      useAuthStore.getState().setAuthStatus(data.oauth_enabled, null)
    }
    return data
  } catch {
    useAuthStore.getState().setAuthStatus(false, null)
    return { oauth_enabled: false, authenticated: false }
  }
}

export function startGitHubLogin() {
  const base = resolveBaseUrl()
  window.location.href = `${base}/api/v1/auth/github/login`
}

export async function logout() {
  const { useAuthStore } = await import('../store/auth')
  await api.post('/api/v1/auth/logout')
  useAuthStore.getState().setAuthStatus(useAuthStore.getState().oauthEnabled, null)
  window.location.href = '/login'
}

/** Open GitHub sign-out in a new tab — use when switching to a different GitHub account. */
export function openGitHubAccountSwitch() {
  window.open('https://github.com/logout', '_blank', 'noopener,noreferrer')
}

export async function listMyRepos(page = 1) {
  const { data } = await api.get('/api/v1/auth/repos', { params: { page } })
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}

export async function submitWorkflow(issueUrl, repoUrl) {
  const { data } = await api.post('/api/v1/workflow/submit', {
    issue_url: issueUrl,
    repo_url: repoUrl,
  })
  return data
}

export async function getTaskStatus(taskUuid) {
  const { data } = await api.get(`/api/v1/workflow/${taskUuid}/status`)
  return data
}

export async function retryTask(taskUuid) {
  const { data } = await api.post(`/api/v1/workflow/${taskUuid}/retry`)
  return data
}

export async function listTasks(status) {
  const params = status ? { status } : {}
  const { data } = await api.get('/api/v1/status/tasks', { params })
  if (Array.isArray(data)) return data
  return data.items ?? []
}

export async function getTaskLogs(taskUuid) {
  const { data } = await api.get(`/api/v1/logs/${taskUuid}/logs`)
  return data
}

export async function syncRepoIndex(repo, forceFull = false) {
  const { data } = await api.post('/api/v1/indexing/sync', {
    repo,
    force_full: forceFull,
  })
  return data
}

export function extractErrorMessage(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return err?.message || 'Something went wrong'
}

export function parseIssueRepo(issueUrl) {
  try {
    const url = new URL(issueUrl.trim())
    const parts = url.pathname.split('/').filter(Boolean)
    if (parts.length >= 2 && url.hostname.includes('github')) {
      return `${parts[0]}/${parts[1]}`
    }
  } catch {
    /* ignore */
  }
  return ''
}

export function repoToUrl(repo) {
  const trimmed = repo.trim()
  if (!trimmed) return ''
  if (trimmed.startsWith('http')) return trimmed.replace(/\/$/, '')
  return `https://github.com/${trimmed.replace(/^\/+|\/+$/g, '')}`
}
