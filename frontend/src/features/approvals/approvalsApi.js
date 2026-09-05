import { apiSlice } from '../../shared/api/apiSlice'

export const approvalsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getApprovals: builder.query({
      query: (params) => ({ url: '/approvals', params }),
      providesTags: ['Approval'],
    }),
    getApproval: builder.query({
      query: (id) => `/approvals/${id}`,
      providesTags: (r, e, id) => [{ type: 'Approval', id }],
    }),
    approveRequest: builder.mutation({
      query: ({ id, reason = '' }) => ({
        url: `/approvals/${id}/approve`,
        method: 'POST',
        body: { reason },
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Approval', id }, 'Approval', 'Quotation'],
    }),
    rejectRequest: builder.mutation({
      query: ({ id, reason }) => ({
        url: `/approvals/${id}/reject`,
        method: 'POST',
        body: { reason },
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Approval', id }, 'Approval', 'Quotation'],
    }),
    returnRequest: builder.mutation({
      query: ({ id, reason }) => ({
        url: `/approvals/${id}/return`,
        method: 'POST',
        body: { reason },
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Approval', id }, 'Approval', 'Quotation'],
    }),
  }),
})

export const {
  useGetApprovalsQuery,
  useGetApprovalQuery,
  useApproveRequestMutation,
  useRejectRequestMutation,
  useReturnRequestMutation,
} = approvalsApi
