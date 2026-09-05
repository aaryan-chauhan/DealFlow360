import { apiSlice } from '../../shared/api/apiSlice'

export const pricingApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getDiscountTiers: builder.query({
      query: () => '/config/discount-tiers',
      providesTags: ['DiscountTier'],
    }),
    createDiscountTier: builder.mutation({
      query: (body) => ({ url: '/config/discount-tiers', method: 'POST', body }),
      invalidatesTags: ['DiscountTier'],
    }),
    updateDiscountTier: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/config/discount-tiers/${id}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['DiscountTier'],
    }),
    createCategoryCeiling: builder.mutation({
      query: (body) => ({ url: '/config/category-ceilings', method: 'POST', body }),
      invalidatesTags: ['DiscountTier'],
    }),
    updateCategoryCeiling: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/config/category-ceilings/${id}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['DiscountTier'],
    }),
    deleteCategoryCeiling: builder.mutation({
      query: (id) => ({ url: `/config/category-ceilings/${id}`, method: 'DELETE' }),
      invalidatesTags: ['DiscountTier'],
    }),
    getApprovalChains: builder.query({
      query: () => '/config/approval-chains',
      providesTags: ['ApprovalChain'],
    }),
    createApprovalChain: builder.mutation({
      query: (body) => ({ url: '/config/approval-chains', method: 'POST', body }),
      // A chain change re-derives the "Approval Chain" column on every tier.
      invalidatesTags: ['ApprovalChain', 'DiscountTier'],
    }),
    updateApprovalChain: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/config/approval-chains/${id}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['ApprovalChain', 'DiscountTier'],
    }),
  }),
})

export const {
  useGetDiscountTiersQuery,
  useCreateDiscountTierMutation,
  useUpdateDiscountTierMutation,
  useCreateCategoryCeilingMutation,
  useUpdateCategoryCeilingMutation,
  useDeleteCategoryCeilingMutation,
  useGetApprovalChainsQuery,
  useCreateApprovalChainMutation,
  useUpdateApprovalChainMutation,
} = pricingApi
