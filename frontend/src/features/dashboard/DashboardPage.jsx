import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { selectActiveMembership, selectCurrentUser } from '../../auth/authSlice'
import { useGetDashboardSummaryQuery } from './dashboardApi'

const STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-700 border-slate-300',
  pending_approval: 'bg-amber-50 text-amber-700 border-amber-300',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  negotiation: 'bg-sky-50 text-sky-700 border-sky-300',
  confirmed: 'bg-indigo-50 text-indigo-700 border-indigo-300',
  rejected: 'bg-rose-50 text-rose-700 border-rose-300',
}

function formatCurrency(amount) {
  const num = parseFloat(amount || 0)
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num)
}

export default function DashboardPage() {
  const user = useSelector(selectCurrentUser)
  const membership = useSelector(selectActiveMembership)
  const { data, isLoading, isError, refetch } = useGetDashboardSummaryQuery()

  const role = membership?.role?.code
  const isManagerOrAdmin = ['sales_manager', 'finance_ops', 'admin'].includes(role)

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
          <p className="text-sm font-medium">Loading sales dashboard...</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-800">
        <p className="font-semibold">Unable to load dashboard metrics.</p>
        <button
          onClick={() => refetch()}
          className="mt-3 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700"
        >
          Retry Loading
        </button>
      </div>
    )
  }

  const { pipeline, approvals, subscriptions, fulfillment, invoicing, recent_quotations } = data

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-2xl bg-gradient-to-r from-ink-900 via-slate-900 to-brand-950 p-6 text-white shadow-lg">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Welcome back, {user?.full_name || user?.email?.split('@')[0]}!
          </h1>
          <p className="mt-1 text-sm text-slate-300">
            {membership?.company?.name || 'DealFlow360'} • Role:{' '}
            <span className="font-medium text-brand-400">{membership?.role?.label}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/quotations/new"
            className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-brand-500 transition"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Quotation
          </Link>
        </div>
      </div>

      {/* Primary Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Pipeline Value */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Active Pipeline
            </span>
            <span className="rounded-lg bg-emerald-50 p-2 text-emerald-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">
            {formatCurrency(pipeline.total_value)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Across <span className="font-semibold text-slate-700">{pipeline.total_count}</span> total deal(s)
          </p>
        </div>

        {/* Pending Approvals */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Pending Approvals
            </span>
            <span className="rounded-lg bg-amber-50 p-2 text-amber-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">
            {approvals.pending_count}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {isManagerOrAdmin ? 'Awaiting your review' : 'Currently in review queue'}
          </p>
        </div>

        {/* Recurring Revenue / Subscriptions */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Monthly Recurring (MRR)
            </span>
            <span className="rounded-lg bg-indigo-50 p-2 text-indigo-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">
            {formatCurrency(subscriptions.mrr)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            From <span className="font-semibold text-slate-700">{subscriptions.active_count}</span> active plan(s)
          </p>
        </div>

        {/* Outstanding Invoices */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Balance Due
            </span>
            <span className="rounded-lg bg-rose-50 p-2 text-rose-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </span>
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">
            {formatCurrency(invoicing.balance_due)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Collected <span className="font-semibold text-emerald-600">{formatCurrency(invoicing.total_paid)}</span>
          </p>
        </div>
      </div>

      {/* Pipeline Breakdown & Fulfillment Status */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Deal Status Breakdown Bar */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Quotation Pipeline Stages</h2>
          <p className="text-xs text-slate-500">Distribution of active deals across governance stages</p>

          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-500">Draft</span>
              <p className="mt-1 text-xl font-bold text-slate-800">{pipeline.by_status.draft || 0}</p>
            </div>
            <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3">
              <span className="text-xs font-medium text-amber-700">Pending Approval</span>
              <p className="mt-1 text-xl font-bold text-amber-800">{pipeline.by_status.pending_approval || 0}</p>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3">
              <span className="text-xs font-medium text-emerald-700">Approved</span>
              <p className="mt-1 text-xl font-bold text-emerald-800">{pipeline.by_status.approved || 0}</p>
            </div>
            <div className="rounded-xl border border-sky-100 bg-sky-50/50 p-3">
              <span className="text-xs font-medium text-sky-700">Customer Negotiation</span>
              <p className="mt-1 text-xl font-bold text-sky-800">{pipeline.by_status.negotiation || 0}</p>
            </div>
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
              <span className="text-xs font-medium text-indigo-700">Confirmed / Won</span>
              <p className="mt-1 text-xl font-bold text-indigo-800">{pipeline.by_status.confirmed || 0}</p>
            </div>
            <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-3">
              <span className="text-xs font-medium text-rose-700">Rejected</span>
              <p className="mt-1 text-xl font-bold text-rose-800">{pipeline.by_status.rejected || 0}</p>
            </div>
          </div>
        </div>

        {/* Fulfillment Quick Overview */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Fulfillment Status</h2>
          <p className="text-xs text-slate-500">Warehouse split orders overview</p>

          <div className="mt-6 space-y-3">
            <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-600">Split Suggested</span>
              <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold text-slate-800">
                {fulfillment.suggested || 0}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-emerald-50 p-3">
              <span className="text-xs font-medium text-emerald-800">Split Accepted</span>
              <span className="rounded-full bg-emerald-200 px-2.5 py-0.5 text-xs font-semibold text-emerald-900">
                {fulfillment.accepted || 0}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-amber-50 p-3">
              <span className="text-xs font-medium text-amber-800">Partially Backordered</span>
              <span className="rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                {fulfillment.backordered || 0}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-indigo-50 p-3">
              <span className="text-xs font-medium text-indigo-800">Fully Fulfilled</span>
              <span className="rounded-full bg-indigo-200 px-2.5 py-0.5 text-xs font-semibold text-indigo-900">
                {fulfillment.fulfilled || 0}
              </span>
            </div>
          </div>

          <div className="mt-4 pt-2">
            <Link
              to="/fulfillment"
              className="block w-full rounded-xl border border-slate-200 bg-slate-50 text-center py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
            >
              Open Fulfillment Workspace ➔
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Activity Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Pending Approvals Widget (if any) */}
        {isManagerOrAdmin && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Approvals Requiring Action</h2>
                <p className="text-xs text-slate-500">Deals exceeding discount ceilings waiting for review</p>
              </div>
              <Link to="/approvals" className="text-xs font-semibold text-brand-600 hover:underline">
                View All
              </Link>
            </div>

            {approvals.pending_requests.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-500">
                No deals currently pending your approval.
              </div>
            ) : (
              <div className="mt-4 divide-y divide-slate-100">
                {approvals.pending_requests.map((req) => (
                  <div key={req.id} className="flex items-center justify-between py-3">
                    <div>
                      <Link to={`/approvals/${req.id}`} className="font-semibold text-sm text-slate-900 hover:text-brand-600">
                        {req.quotation_number}
                      </Link>
                      <p className="text-xs text-slate-500">{req.customer_name} • Risk Score: <span className="font-medium text-rose-600">{req.risk_score_snapshot}</span></p>
                    </div>
                    <Link
                      to={`/approvals/${req.id}`}
                      className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 transition"
                    >
                      Review
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Recent Quotations Widget */}
        <div className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-sm ${!isManagerOrAdmin ? 'lg:col-span-2' : ''}`}>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Recent Quotations</h2>
              <p className="text-xs text-slate-500">Latest deals created in the workspace</p>
            </div>
            <Link to="/quotations" className="text-xs font-semibold text-brand-600 hover:underline">
              View All
            </Link>
          </div>

          <div className="mt-4 divide-y divide-slate-100">
            {recent_quotations.map((quote) => (
              <div key={quote.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 font-bold text-xs text-slate-700">
                    Q
                  </div>
                  <div>
                    <Link to={`/quotations/${quote.id}`} className="font-semibold text-sm text-slate-900 hover:text-brand-600">
                      {quote.number}
                    </Link>
                    <p className="text-xs text-slate-500">{quote.customer_name}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <span className={`rounded-md border px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[quote.status]}`}>
                    {quote.status_display}
                  </span>
                  <span className="text-sm font-semibold text-slate-900">
                    {formatCurrency(quote.total_value)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
