import { apiBaseUrl, apiSlice } from '../../shared/api/apiSlice'

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

/** Export isn't RTK Query — it's a file download, and RTK Query has no way to hand the
 * browser a blob to save. Builds the same filter params the summary uses, so what a rep
 * sees on screen is exactly what the exported file contains. `token` must come from
 * `selectAccessToken` — it does not live under a plain `localStorage` key. */
export async function downloadReport(token, { format, ...filters }) {
  const cleanParams = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  )
  const params = new URLSearchParams({ format, ...cleanParams })
  const response = await fetch(`${apiBaseUrl}/reports/export?${params.toString()}`, {
    headers: { Authorization: token ? `Bearer ${token}` : '' },
  })
  if (!response.ok) {
    throw new Error(`Export failed (${response.status})`)
  }
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `dealflow_sales_report.${format === 'pdf' ? 'pdf' : 'xlsx'}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
