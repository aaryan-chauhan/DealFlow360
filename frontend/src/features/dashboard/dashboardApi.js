import { apiSlice } from '../../shared/api/apiSlice'

export const dashboardApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getDashboardSummary: builder.query({
      query: () => '/dashboard/summary',
      providesTags: ['Quotations', 'Approvals', 'Subscriptions', 'Fulfillment', 'Invoices'],
    }),
  }),
})

export const { useGetDashboardSummaryQuery } = dashboardApi
