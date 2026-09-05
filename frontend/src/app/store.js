import { configureStore } from '@reduxjs/toolkit'

import authReducer from '../auth/authSlice'
import { apiSlice } from '../shared/api/apiSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(apiSlice.middleware),
})
