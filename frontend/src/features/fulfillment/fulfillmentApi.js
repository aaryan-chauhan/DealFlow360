import { apiSlice } from '../../shared/api/apiSlice'

export const fulfillmentApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getFulfillmentOrders: builder.query({
      query: (params) => ({ url: '/fulfillment/orders', params }),
      providesTags: ['Fulfillment'],
    }),
    getFulfillmentOrder: builder.query({
      query: (id) => `/fulfillment/${id}`,
      providesTags: (r, e, id) => [{ type: 'Fulfillment', id }],
    }),
    acceptSplit: builder.mutation({
      query: (id) => ({ url: `/fulfillment/${id}/accept-split`, method: 'POST' }),
      invalidatesTags: (r, e, id) => [{ type: 'Fulfillment', id }, 'Fulfillment'],
    }),
    overrideSplit: builder.mutation({
      query: ({ id, lines, reason = '' }) => ({
        url: `/fulfillment/${id}/override`,
        method: 'POST',
        body: { lines, reason },
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Fulfillment', id }, 'Fulfillment'],
    }),
    consolidateBackorder: builder.mutation({
      query: ({ id, lineIds }) => ({
        url: `/fulfillment/${id}/consolidate-backorder`,
        method: 'POST',
        body: lineIds ? { line_ids: lineIds } : {},
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Fulfillment', id }, 'Fulfillment'],
    }),
    notifyBackorderCustomer: builder.mutation({
      query: ({ id, note = '' }) => ({
        url: `/fulfillment/${id}/notify-customer`,
        method: 'POST',
        body: { note },
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Fulfillment', id }],
    }),
    // Stand-in for the Celery Beat replenishment watcher until Celery is wired (§7.2.6).
    scanReplenishment: builder.mutation({
      query: () => ({ url: '/fulfillment/scan-replenishment', method: 'POST' }),
      invalidatesTags: ['Fulfillment'],
    }),
  }),
})

export const {
  useGetFulfillmentOrdersQuery,
  useGetFulfillmentOrderQuery,
  useAcceptSplitMutation,
  useOverrideSplitMutation,
  useConsolidateBackorderMutation,
  useNotifyBackorderCustomerMutation,
  useScanReplenishmentMutation,
} = fulfillmentApi
