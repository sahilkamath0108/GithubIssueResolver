import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'

export function RequireAuth({ children }) {
  const location = useLocation()
  const oauthEnabled = useAuthStore((s) => s.oauthEnabled)
  const user = useAuthStore((s) => s.user)
  const checked = useAuthStore((s) => s.checked)

  if (!checked) return children
  if (!oauthEnabled) return children
  if (user) return children

  return <Navigate to="/login" state={{ from: location.pathname }} replace />
}
