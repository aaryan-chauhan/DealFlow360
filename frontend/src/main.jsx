import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { Provider } from 'react-redux'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import App from './app/App'
import { store } from './app/store'
import './index.css'

// The customer portal is split out here rather than inside `App` on purpose (spec §10).
//
// Two things fall out of doing it at this level, and both are the point:
//
//  1. The workspace `<Provider store={store}>` wraps only the workspace tree. The portal
//     never has the internal store in scope, so no portal component can read the auth
//     slice — not by accident, not by a copy-pasted `useSelector`. It brings its own
//     store (`portalStore`) with no auth slice in it at all.
//  2. `lazy` puts the portal in its own chunk. A customer opening a quotation link never
//     downloads the workspace bundle, and the workspace never downloads the portal's.
//
// This is the security boundary described in §3 and §5.9, expressed as module structure
// rather than as a rule someone has to remember.
const PortalApp = lazy(() => import('./features/portal/PortalApp'))

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route
          path="/portal/*"
          element={
            <Suspense
              fallback={<p className="mt-24 text-center text-sm text-slate-500">Loading…</p>}
            >
              <PortalApp />
            </Suspense>
          }
        />
        <Route
          path="*"
          element={
            <Provider store={store}>
              <App />
            </Provider>
          }
        />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
