import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

// Deliberately a *separate* createApi from `shared/api/apiSlice`, not an injectEndpoints
// on it. Sharing the internal slice would mean sharing its `prepareHeaders`, and that
// function reaches into `state.auth.access` — a workspace JWT would then ride along on
// every portal request from a machine where someone happens to be logged in.
//
// Three properties this file has to keep:
//   1. baseUrl ends in /api/portal — there is no way to spell a path that escapes it.
//   2. prepareHeaders is absent. No Authorization header is ever attached.
//   3. The portal token lives in the URL, comes from the route, and is never written to
//      localStorage or sessionStorage. Closing the tab ends the session, and nothing the
//      customer does leaves a credential behind on a shared machine.
const portalBaseUrl =
  (import.meta.env.VITE_API_BASE_URL ??
    `${window.location.protocol}//${window.location.hostname}:8000/api`) + '/portal'

export const portalApi = createApi({
  reducerPath: 'portalApi',
  baseQuery: fetchBaseQuery({ baseUrl: portalBaseUrl }),
  tagTypes: ['PortalQuotation', 'MyQuotations'],
  endpoints: (builder) => ({
    // The customer's second entry point (spec A1): email + password instead of a
    // rep-sent link, in exchange for a customer-scoped token (never a JWT, never
    // workspace-wide) good for listing and opening this customer's own quotations.
    loginCustomer: builder.mutation({
      query: (body) => ({ url: '/login', method: 'POST', body }),
    }),
    getMyQuotations: builder.query({
      query: (token) => `/me/quotations/${token}`,
      providesTags: ['MyQuotations'],
    }),
    // Mints an ordinary single-quotation session for one of the customer's own deals —
    // the caller then opens `/portal/quotations/{token}` exactly like a rep-sent link.
    openQuotation: builder.mutation({
      query: ({ token, quotationId }) => ({
        url: `/me/quotations/${token}/${quotationId}/open`,
        method: 'POST',
      }),
    }),
    getPortalQuotation: builder.query({
      query: (token) => `/quotations/${token}`,
      providesTags: ['PortalQuotation'],
    }),
    postComment: builder.mutation({
      query: ({ token, ...body }) => ({ url: `/${token}/comment`, method: 'POST', body }),
      invalidatesTags: ['PortalQuotation'],
    }),
    postCounterOffer: builder.mutation({
      query: ({ token, ...body }) => ({
        url: `/${token}/counter-offer`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['PortalQuotation'],
    }),
    confirmQuotation: builder.mutation({
      query: ({ token, ...body }) => ({ url: `/${token}/confirm`, method: 'POST', body }),
      invalidatesTags: ['PortalQuotation'],
    }),
    postDeliveryDateRequest: builder.mutation({
      query: ({ token, ...body }) => ({
        url: `/${token}/request-delivery-date`,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['PortalQuotation'],
    }),
  }),
})

export const {
  useLoginCustomerMutation,
  useGetMyQuotationsQuery,
  useOpenQuotationMutation,
  useGetPortalQuotationQuery,
  usePostCommentMutation,
  usePostCounterOfferMutation,
  useConfirmQuotationMutation,
  usePostDeliveryDateRequestMutation,
} = portalApi
