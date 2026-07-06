export const STEP_ORDER = ['plan', 'search', 'write', 'test', 'pr']

export const STEP_LABELS = {
  plan: 'Plan',
  search: 'Search',
  write: 'Write',
  test: 'Test',
  pr: 'Pull Request',
}

const BACKEND_TO_STEP = {
  planning: 'plan',
  plan: 'plan',
  reading_code: 'search',
  read_code: 'search',
  writing_code: 'write',
  write_code: 'write',
  executing_tests: 'test',
  execute: 'test',
  creating_pr: 'pr',
  create_pr: 'pr',
}

export function parseIssueNumber(issueUrl) {
  const m = String(issueUrl || '').match(/issues\/(\d+)/)
  return m ? Number.parseInt(m[1], 10) : null
}

export function parseRepoFromUrl(url) {
  try {
    const u = new URL(url)
    const parts = u.pathname.split('/').filter(Boolean)
    if (parts.length >= 2) return `${parts[0]}/${parts[1]}`
  } catch {
    /* ignore */
  }
  return url || 'unknown/repo'
}

export function issueTitleFromUrl(issueUrl) {
  const num = parseIssueNumber(issueUrl)
  return num ? `Issue #${num}` : 'GitHub issue'
}

export function backendStepToKey(step) {
  if (!step) return 'plan'
  const lower = step.toLowerCase()
  if (lower.startsWith('fixing_retry')) return 'test'
  if (lower.endsWith('_failed')) {
    const base = lower.replace('_failed', '')
    return BACKEND_TO_STEP[base] || 'plan'
  }
  return BACKEND_TO_STEP[lower] || 'plan'
}

export function buildPipelineSteps(currentStep, status) {
  const activeKey = backendStepToKey(currentStep)
  const activeIdx = Math.max(0, STEP_ORDER.indexOf(activeKey))
  const isSuccess = status === 'success'
  const isFailed = status === 'failed'
  const isCancelled = status === 'cancelled'
  const isActive = status === 'running' || status === 'queued'

  return STEP_ORDER.map((key, i) => {
    let stepStatus = 'pending'
    if (isSuccess) stepStatus = 'done'
    else if (isCancelled) stepStatus = i <= activeIdx ? 'done' : 'pending'
    else if (isFailed && i < activeIdx) stepStatus = 'done'
    else if (isFailed && i === activeIdx) stepStatus = 'failed'
    else if (isFailed && i > activeIdx) stepStatus = 'pending'
    else if (i < activeIdx) stepStatus = 'done'
    else if (i === activeIdx && isActive) stepStatus = status === 'queued' ? 'pending' : 'running'
    return { key, label: STEP_LABELS[key], status: stepStatus }
  })
}

export function computeProgress(steps) {
  const done = steps.filter((s) => s.status === 'done').length
  const running = steps.some((s) => s.status === 'running')
  const base = Math.round((done / steps.length) * 100)
  if (running) return Math.min(99, base + Math.round(100 / steps.length / 2))
  if (done === steps.length) return 100
  return base
}

export function weeklyThroughput(tasks) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const buckets = days.map((day) => ({ day, resolved: 0, failed: 0 }))
  const now = new Date()
  const start = new Date(now)
  start.setDate(start.getDate() - 6)
  start.setHours(0, 0, 0, 0)

  for (const task of tasks) {
    const created = new Date(task.created_at)
    if (created < start) continue
    const idx = created.getDay()
    if (task.status === 'success') buckets[idx].resolved += 1
    else if (task.status === 'failed') buckets[idx].failed += 1
  }

  const ordered = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    ordered.push(buckets[d.getDay()])
  }
  return ordered
}
