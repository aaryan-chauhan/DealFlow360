import { apiSlice } from '../../shared/api/apiSlice'

export const quotationsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getQuotations: builder.query({
      query: (params) => ({ url: '/quotations', params }),
      providesTags: ['Quotation'],
    }),
    getQuotation: builder.query({
      query: (id) => `/quotations/${id}`,
      providesTags: (result, error, id) => [{ type: 'Quotation', id }],
    }),
    createQuotation: builder.mutation({
      query: (body) => ({ url: '/quotations', method: 'POST', body }),
      invalidatesTags: ['Quotation'],
    }),
    addLine: builder.mutation({
      query: ({ quotationId, ...body }) => ({
        url: `/quotations/${quotationId}/lines`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { quotationId }) => [{ type: 'Quotation', id: quotationId }, 'Quotation'],
    }),
    updateLine: builder.mutation({
      query: ({ quotationId, lineId, ...body }) => ({
        url: `/quotations/${quotationId}/lines/${lineId}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (r, e, { quotationId }) => [
        { type: 'Quotation', id: quotationId },
        'Quotation',
        'Approval',
      ],
    }),
    deleteLine: builder.mutation({
      query: ({ quotationId, lineId }) => ({
        url: `/quotations/${quotationId}/lines/${lineId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (r, e, { quotationId }) => [
        { type: 'Quotation', id: quotationId },
        'Quotation',
        'Approval',
      ],
    }),
    submitForApproval: builder.mutation({
      query: (id) => ({ url: `/quotations/${id}/submit-for-approval`, method: 'POST', body: {} }),
      invalidatesTags: (r, e, id) => [{ type: 'Quotation', id }, 'Quotation', 'Approval'],
    }),
    getCustomers: builder.query({
      query: (search) => ({ url: '/customers', params: search ? { search } : undefined }),
      providesTags: ['Customer'],
    }),
    createCustomer: builder.mutation({
      query: (body) => ({ url: '/customers', method: 'POST', body }),
      invalidatesTags: ['Customer'],
    }),
  }),
})

export const {
  useGetQuotationsQuery,
  useGetQuotationQuery,
  useCreateQuotationMutation,
  useAddLineMutation,
  useUpdateLineMutation,
  useDeleteLineMutation,
  useSubmitForApprovalMutation,
  useGetCustomersQuery,
  useCreateCustomerMutation,
} = quotationsApi
