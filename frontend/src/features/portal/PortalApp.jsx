import { Provider } from 'react-redux'
import { Navigate, Route, Routes } from 'react-router-dom'

import PortalLoginPage from './PortalLoginPage'
import PortalMyQuotationsPage from './PortalMyQuotationsPage'
import PortalNegotiationPage from './PortalNegotiationPage'
import { portalStore } from './portalStore'

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
          <Route path="my-quotations/:token" element={<PortalMyQuotationsPage />} />
          <Route path="" element={<PortalLoginPage />} />
          <Route path="*" element={<Navigate to="/portal" replace />} />
        </Routes>
      </div>
    </Provider>
  )
}
