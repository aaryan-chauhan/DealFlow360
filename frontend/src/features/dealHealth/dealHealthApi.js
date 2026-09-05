import { apiSlice } from '../../shared/api/apiSlice'

export const dealHealthApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getAlerts: builder.query({
      query: (params) => ({
        url: 'deal-health/alerts',
        params,
      }),
      providesTags: (result = []) => [
        { type: 'AnomalyAlert', id: 'LIST' },
        ...result.map((a) => ({ type: 'AnomalyAlert', id: a.id })),
      ],
    }),
    triggerScan: builder.mutation({
      query: () => ({
        url: 'deal-health/alerts/scan/',
        method: 'POST',
      }),
      invalidatesTags: [{ type: 'AnomalyAlert', id: 'LIST' }],
    }),
    escalateAlert: builder.mutation({
      query: ({ id, note }) => ({
        url: `deal-health/alerts/${id}/escalate/`,
        method: 'POST',
        body: { note },
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'AnomalyAlert', id: 'LIST' },
        { type: 'AnomalyAlert', id },
      ],
    }),
    nudgeAlert: builder.mutation({
      query: (id) => ({
        url: `deal-health/alerts/${id}/nudge/`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [
        { type: 'AnomalyAlert', id: 'LIST' },
        { type: 'AnomalyAlert', id },
      ],
    }),
  }),
})

export const {
  useGetAlertsQuery,
  useTriggerScanMutation,
  useEscalateAlertMutation,
  useNudgeAlertMutation,
} = dealHealthApi
