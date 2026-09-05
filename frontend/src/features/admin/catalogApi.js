import { apiSlice } from '../../shared/api/apiSlice'

export const catalogApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getProducts: builder.query({
      query: (search) => ({ url: '/products', params: search ? { search } : undefined }),
      providesTags: ['Product'],
    }),
    createProduct: builder.mutation({
      query: (body) => ({ url: '/products', method: 'POST', body }),
      invalidatesTags: ['Product'],
    }),
    updateProduct: builder.mutation({
      query: ({ id, ...body }) => ({ url: `/products/${id}`, method: 'PATCH', body }),
      invalidatesTags: ['Product'],
    }),
    deleteProduct: builder.mutation({
      query: (id) => ({ url: `/products/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Product'],
    }),
    createVariant: builder.mutation({
      query: ({ productId, ...body }) => ({
        url: `/products/${productId}/variants`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Product'],
    }),
    getPriceLists: builder.query({
      query: () => '/price-lists',
      providesTags: ['PriceList'],
    }),
    createPriceList: builder.mutation({
      query: (body) => ({ url: '/price-lists', method: 'POST', body }),
      invalidatesTags: ['PriceList'],
    }),
  }),
})

export const {
  useGetProductsQuery,
  useCreateProductMutation,
  useUpdateProductMutation,
  useDeleteProductMutation,
  useCreateVariantMutation,
  useGetPriceListsQuery,
  useCreatePriceListMutation,
} = catalogApi
