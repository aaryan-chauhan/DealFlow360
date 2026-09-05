import { createSlice } from '@reduxjs/toolkit'

const STORAGE_KEY = 'df360.auth'

function safe(fn, fallback = null) {
  try {
    return fn()
  } catch {
    return fallback
  }
}

// "Remember me" decides which store the session lands in: localStorage survives a
// browser restart, sessionStorage dies with the tab.
let store = safe(() => (localStorage.getItem(STORAGE_KEY) ? localStorage : sessionStorage), null)

function loadState() {
  return safe(() => {
    const raw = localStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  })
}

function persist(state) {
  safe(() => {
    localStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(STORAGE_KEY)
    if (state.access) {
      const target = store ?? sessionStorage
      target.setItem(
        STORAGE_KEY,
        JSON.stringify({ user: state.user, access: state.access, refresh: state.refresh }),
      )
    }
  })
}

const stored = loadState()

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: stored?.user ?? null,
    access: stored?.access ?? null,
    refresh: stored?.refresh ?? null,
  },
  reducers: {
    credentialsReceived(state, action) {
      const { user, access, refresh, remember } = action.payload
      if (remember !== undefined) {
        store = safe(() => (remember ? localStorage : sessionStorage), null)
      }
      if (user !== undefined) state.user = user
      if (access) state.access = access
      if (refresh) state.refresh = refresh
      persist(state)
    },
    loggedOut(state) {
      state.user = null
      state.access = null
      state.refresh = null
      persist(state)
    },
  },
})

export const { credentialsReceived, loggedOut } = authSlice.actions
export const selectCurrentUser = (state) => state.auth.user

/** The company + role the user is acting as — every RBAC decision in the UI reads this. */
export const selectActiveMembership = (state) => {
  const memberships = state.auth.user?.memberships ?? []
  return memberships.find((m) => m.is_active_default) ?? memberships[0] ?? null
}
export const selectActiveRole = (state) => selectActiveMembership(state)?.role?.code ?? null

export const selectRefreshToken = (state) => state.auth.refresh
export const selectIsAuthenticated = (state) => Boolean(state.auth.access)
export default authSlice.reducer
