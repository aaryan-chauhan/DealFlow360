import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

import { credentialsReceived, loggedOut } from '../../auth/authSlice'

// Same host the app was served from, port 8000. Opened at http://192.168.9.23:5173
// the API is http://192.168.9.23:8000/api; at localhost it stays localhost. Set
// VITE_API_BASE_URL to override (e.g. a deployed API on a different host).
export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  `${window.location.protocol}//${window.location.hostname}:8000/api`

const baseQuery = fetchBaseQuery({
  baseUrl: apiBaseUrl,
  prepareHeaders: (headers, { getState }) => {
    const token = getState().auth.access
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return headers
  },
})

async function baseQueryWithReauth(args, api, extraOptions) {
  let result = await baseQuery(args, api, extraOptions)

  if (result.error?.status === 401) {
    const refresh = api.getState().auth.refresh
    if (!refresh) {
      api.dispatch(loggedOut())
      return result
    }
    const refreshResult = await baseQuery(
      { url: '/auth/refresh', method: 'POST', body: { refresh } },
      api,
      extraOptions,
    )
    if (refreshResult.data?.access) {
      api.dispatch(credentialsReceived(refreshResult.data))
      result = await baseQuery(args, api, extraOptions)
    } else {
      api.dispatch(loggedOut())
    }
  }

  return result
}

export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    'Me',
    'Product',
    'PriceList',
    'DiscountTier',
    'ApprovalChain',
    'Customer',
    'Quotation',
    'Approval',
    'Fulfillment',
    'Subscription',
    'SubscriptionPlan',
    'Invoice',
  ],
  endpoints: () => ({}),
})
