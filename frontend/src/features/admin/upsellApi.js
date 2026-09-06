import { apiSlice } from '../../shared/api/apiSlice'

export const upsellApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getUpsellRules: builder.query({
      query: () => '/upsell-rules',
      providesTags: ['UpsellRule'],
    }),
    createUpsellRule: builder.mutation({
      query: (body) => ({ url: '/upsell-rules', method: 'POST', body }),
      invalidatesTags: ['UpsellRule'],
    }),
    updateUpsellRule: builder.mutation({
      query: ({ id, ...body }) => ({ url: `/upsell-rules/${id}`, method: 'PATCH', body }),
      invalidatesTags: ['UpsellRule'],
    }),
    deleteUpsellRule: builder.mutation({
      query: (id) => ({ url: `/upsell-rules/${id}`, method: 'DELETE' }),
      invalidatesTags: ['UpsellRule'],
    }),
  }),
})

export const {
  useGetUpsellRulesQuery,
  useCreateUpsellRuleMutation,
  useUpdateUpsellRuleMutation,
  useDeleteUpsellRuleMutation,
} = upsellApi
