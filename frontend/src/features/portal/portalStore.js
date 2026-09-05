import { configureStore } from '@reduxjs/toolkit'

import { portalApi } from './portalApi'

/**
 * The portal's own Redux store (spec §10).
 *
 * It has exactly one reducer — the portal API cache. There is no `auth` slice, so there
 * is nothing in this store that could hold or leak a workspace session, and no portal
 * component can reach the internal store even by accident: `PortalApp` mounts this
 * Provider, and the workspace's Provider never wraps the portal tree at all (see
 * `main.jsx`). A stray `useSelector((s) => s.auth)` inside the portal does not read the
 * wrong value — it reads `undefined`.
 */
export const portalStore = configureStore({
  reducer: {
    [portalApi.reducerPath]: portalApi.reducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(portalApi.middleware),
})
