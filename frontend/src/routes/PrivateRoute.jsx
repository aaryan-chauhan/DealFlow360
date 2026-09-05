import { useSelector } from 'react-redux'
import { Navigate, useLocation } from 'react-router-dom'

import { selectActiveMembership, selectIsAuthenticated } from '../auth/authSlice'

function AccessDenied({ membership, roles }) {
  return (
    <div className="mx-auto max-w-lg rounded-xl border border-amber-200 bg-amber-50 p-8">
      <h1 className="text-lg font-semibold text-amber-900">403 — Not available for your role</h1>
      <p className="mt-2 text-sm text-amber-800">
        You are signed in as <strong>{membership?.role?.label ?? 'no role'}</strong>. This screen is
        restricted to: <strong>{roles.join(', ')}</strong>.
      </p>
      <p className="mt-3 text-xs text-amber-700">
        The API enforces the same rule independently — write calls from this role return HTTP 403
        even if this screen is reached directly.
      </p>
    </div>
  )
}

export default function PrivateRoute({ roles, children }) {
  const isAuthenticated = useSelector(selectIsAuthenticated)
  const membership = useSelector(selectActiveMembership)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (roles && !roles.includes(membership?.role?.code)) {
    return <AccessDenied membership={membership} roles={roles} />
  }
  return children
}
