import { apiSlice } from '../../shared/api/apiSlice'

export const adminApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getWarehouses: builder.query({
      query: () => '/warehouses',
      providesTags: ['Warehouses'],
    }),
    createWarehouse: builder.mutation({
      query: (body) => ({
        url: '/warehouses',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Warehouses', 'Fulfillment'],
    }),
    updateWarehouse: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/warehouses/${id}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['Warehouses', 'Fulfillment'],
    }),
    getStockLevels: builder.query({
      query: (params) => ({ url: '/stock-levels', params }),
      providesTags: ['StockLevels'],
    }),
    updateStockLevel: builder.mutation({
      query: ({ id, qty_on_hand }) => ({
        url: `/stock-levels/${id}`,
        method: 'PATCH',
        body: { qty_on_hand },
      }),
      invalidatesTags: ['StockLevels', 'Fulfillment'],
    }),
    getSubscriptionPlans: builder.query({
      query: () => '/subscription-plans',
      providesTags: ['SubscriptionPlans'],
    }),
    createSubscriptionPlan: builder.mutation({
      query: (body) => ({
        url: '/subscription-plans',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['SubscriptionPlans'],
    }),
    updateSubscriptionPlan: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/subscription-plans/${id}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['SubscriptionPlans'],
    }),
  }),
})

export const {
  useGetWarehousesQuery,
  useCreateWarehouseMutation,
  useUpdateWarehouseMutation,
  useGetStockLevelsQuery,
  useUpdateStockLevelMutation,
  useGetSubscriptionPlansQuery,
  useCreateSubscriptionPlanMutation,
  useUpdateSubscriptionPlanMutation,
} = adminApi

