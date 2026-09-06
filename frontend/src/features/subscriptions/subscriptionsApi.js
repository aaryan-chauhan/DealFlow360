import { apiSlice } from '../../shared/api/apiSlice'

export const subscriptionsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getSubscriptions: builder.query({
      query: (params) => ({ url: '/subscriptions', params }),
      providesTags: ['Subscription'],
    }),
    // Screen 10 loads through §8's /billing/{id} route rather than /subscriptions/{id}:
    // same payload, but the billing screen is what that route exists for.
    getBillingDetail: builder.query({
      query: (id) => `/billing/${id}`,
      providesTags: (r, e, id) => [{ type: 'Subscription', id }],
    }),
    getSubscriptionPlans: builder.query({
      query: () => '/subscription-plans',
      providesTags: ['SubscriptionPlan'],
    }),
    modifySubscription: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/subscriptions/${id}/modify`,
        method: 'POST',
        body,
      }),
      // A change re-prices future cycles and can raise a proration event, so the invoice
      // list is invalidated too — the next billing run will bill a different number.
      invalidatesTags: (r, e, { id }) => [
        { type: 'Subscription', id },
        'Subscription',
        'Invoice',
      ],
    }),
    pauseSubscription: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/subscriptions/${id}/pause`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Subscription', id }, 'Subscription'],
    }),
    resumeSubscription: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/subscriptions/${id}/resume`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { id }) => [{ type: 'Subscription', id }, 'Subscription'],
    }),
    cancelSubscription: builder.mutation({
      query: ({ id, ...body }) => ({
        url: `/subscriptions/${id}/cancel`,
        method: 'POST',
        body,
      }),
      invalidatesTags: (r, e, { id }) => [
        { type: 'Subscription', id },
        'Subscription',
        'Invoice',
      ],
    }),
    // Stand-in for the Celery Beat billing run until Celery is wired (§7.3.4).
    runBilling: builder.mutation({
      query: (body = {}) => ({ url: '/billing/run', method: 'POST', body }),
      invalidatesTags: ['Subscription', 'Invoice'],
    }),
  }),
})

export const {
  useGetSubscriptionsQuery,
  useGetBillingDetailQuery,
  useGetSubscriptionPlansQuery,
  useModifySubscriptionMutation,
  usePauseSubscriptionMutation,
  useResumeSubscriptionMutation,
  useCancelSubscriptionMutation,
  useRunBillingMutation,
} = subscriptionsApi
