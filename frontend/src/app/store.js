import { combineReducers, configureStore } from '@reduxjs/toolkit'

import authReducer, { loggedOut } from '../auth/authSlice'
import { apiSlice } from '../shared/api/apiSlice'

const appReducer = combineReducers({
  auth: authReducer,
  [apiSlice.reducerPath]: apiSlice.reducer,
})

// Every cached query result — including permission-sensitive fields like an approval's
// `can_act` — is keyed only by its arguments, not by who's logged in. Without this, a
// client-side logout/login in the same tab (no hard reload) leaves the next person
// signed in reading the previous user's cached API responses until something else
// happens to invalidate them. Wiping the API slice back to its initial state alongside
// the auth slice on every `loggedOut` closes that gap.
function rootReducer(state, action) {
  if (action.type === loggedOut.type) {
    state = { auth: state?.auth, [apiSlice.reducerPath]: undefined }
  }
  return appReducer(state, action)
}

export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(apiSlice.middleware),
})
