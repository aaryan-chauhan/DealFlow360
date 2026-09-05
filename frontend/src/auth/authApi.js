import { apiSlice } from '../shared/api/apiSlice'

export const authApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    signup: builder.mutation({
      query: (body) => ({ url: '/auth/signup', method: 'POST', body }),
    }),
    login: builder.mutation({
      query: (body) => ({ url: '/auth/login', method: 'POST', body }),
    }),
    logout: builder.mutation({
      query: (body) => ({ url: '/auth/logout', method: 'POST', body }),
    }),
    me: builder.query({
      query: () => '/auth/me',
      providesTags: ['Me'],
    }),
  }),
})

export const { useSignupMutation, useLoginMutation, useLogoutMutation, useMeQuery } = authApi
