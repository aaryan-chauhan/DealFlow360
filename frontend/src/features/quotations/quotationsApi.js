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
      async onQueryStarted(arg, { dispatch, queryFulfilled }) {
        try {
          const { data: created } = await queryFulfilled
          dispatch(
            quotationsApi.util.upsertQueryData('getQuotation', created.id, created)
          )
        } catch {
          /* ignore error */
        }
      },
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
    applyBulkDiscount: builder.mutation({
      query: ({ quotationId, discount_pct }) => ({
        url: `/quotations/${quotationId}/bulk-discount`,
        method: 'POST',
        body: { discount_pct },
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
    // Mints the customer's magic link. The raw token comes back exactly once — the API
    // stores only a hash — so the response is the only chance to show or copy it.
    generatePortalLink: builder.mutation({
      query: (id) => ({
        url: `/quotations/${id}/generate-portal-link`,
        method: 'POST',
        body: {},
      }),
      invalidatesTags: (r, e, id) => [{ type: 'Quotation', id }],
    }),
    // The rep's side of the customer thread. Same rows the portal reads (§5.9), reached
    // through the internal JWT rather than a portal token.
    replyToNegotiation: builder.mutation({
      query: ({ quotationId, ...body }) => ({
        url: `/quotations/${quotationId}/negotiation`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { quotationId }) => [{ type: 'Quotation', id: quotationId }],
    }),
    getCustomers: builder.query({
      query: (search) => ({ url: '/customers', params: search ? { search } : undefined }),
      providesTags: ['Customer'],
    }),
    createCustomer: builder.mutation({
      query: (body) => ({ url: '/customers', method: 'POST', body }),
      invalidatesTags: ['Customer'],
    }),
    getSuggestions: builder.query({
      query: (id) => `/quotations/${id}/suggestions`,
      providesTags: (r, e, id) => [{ type: 'Quotation', id }, 'Suggestions'],
    }),
    addSuggestion: builder.mutation({
      query: ({ quotationId, suggestionId }) => ({
        url: `/quotations/${quotationId}/suggestions/${suggestionId}/add`,
        method: 'POST',
      }),
      invalidatesTags: (r, e, { quotationId }) => [
        { type: 'Quotation', id: quotationId },
        'Quotation',
        'Suggestions',
      ],
    }),
    dismissSuggestion: builder.mutation({
      query: ({ quotationId, suggestionId }) => ({
        url: `/quotations/${quotationId}/suggestions/${suggestionId}/dismiss`,
        method: 'POST',
      }),
      invalidatesTags: (r, e, { quotationId }) => [{ type: 'Quotation', id: quotationId }, 'Suggestions'],
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
  useApplyBulkDiscountMutation,
  useSubmitForApprovalMutation,
  useGeneratePortalLinkMutation,
  useReplyToNegotiationMutation,
  useGetCustomersQuery,
  useCreateCustomerMutation,
  useGetSuggestionsQuery,
  useAddSuggestionMutation,
  useDismissSuggestionMutation,
} = quotationsApi

