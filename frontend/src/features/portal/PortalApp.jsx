import { Provider } from 'react-redux'
import { Navigate, Route, Routes } from 'react-router-dom'

import PortalNegotiationPage from './PortalNegotiationPage'
import { portalStore } from './portalStore'

function MissingLink() {
  return (
    <div className="mx-auto mt-24 max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
      <h1 className="text-lg font-semibold text-slate-900">Nothing to show here</h1>
      <p className="mt-2 text-sm text-slate-600">
        Open the quotation link your account manager sent you. It looks like{' '}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
          /portal/quotations/…
        </code>
        .
      </p>
    </div>
  )
}

/**
 * The customer portal's root (spec §3, §10).
 *
 * The isolation this component provides is structural, not stylistic:
 *
 *  - It mounts `portalStore`, which holds only the portal API cache. The workspace's
 *    `store` — auth slice and all — is never mounted above this tree (see `main.jsx`),
 *    so there is no Provider in scope that could hand a portal component a workspace JWT.
 *  - Its routes are a closed set under `/portal`. There is no link out of here into the
 *    workspace, and `PrivateRoute` is never involved.
 *  - Its only data source is `portalApi`, whose baseUrl is pinned to `/api/portal`.
 *  - The token lives in the route and in React state. Nothing is persisted, so the
 *    session ends with the tab — which is what you want on a customer's shared laptop.
 */
export default function PortalApp() {
  return (
    <Provider store={portalStore}>
      <div className="min-h-screen bg-slate-50">
        <Routes>
          <Route path="quotations/:token" element={<PortalNegotiationPage />} />
          <Route path="" element={<MissingLink />} />
          <Route path="*" element={<Navigate to="/portal" replace />} />
        </Routes>
      </div>
    </Provider>
  )
}
