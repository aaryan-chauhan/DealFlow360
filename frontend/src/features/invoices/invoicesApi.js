import { apiSlice } from '../../shared/api/apiSlice'

export const invoicesApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getInvoices: builder.query({
      query: (params) => ({ url: '/invoices', params }),
      providesTags: ['Invoice'],
    }),
    getInvoice: builder.query({
      query: (id) => `/invoices/${id}`,
      providesTags: (r, e, id) => [{ type: 'Invoice', id }],
    }),
    recordPayment: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/invoices/${id}/record-payment`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Invoice', id }, 'Invoice'],
    }),
    issueCreditNote: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/invoices/${id}/issue-credit-note`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Invoice', id }, 'Invoice'],
    }),
  }),
})

export const {
  useGetInvoicesQuery,
  useGetInvoiceQuery,
  useRecordPaymentMutation,
  useIssueCreditNoteMutation,
} = invoicesApi
