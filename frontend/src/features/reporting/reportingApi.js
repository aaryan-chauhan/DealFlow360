import { apiSlice } from '../../shared/api/apiSlice'

export const reportingApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getReportingSummary: builder.query({
      query: (params) => ({
        url: 'reports/summary',
        params,
      }),
      providesTags: ['Reporting'],
    }),
  }),
})

export const { useGetReportingSummaryQuery } = reportingApi
