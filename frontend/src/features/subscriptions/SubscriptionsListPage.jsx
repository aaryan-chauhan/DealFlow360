import { useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'

import { selectActiveMembership } from '../../auth/authSlice'
import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetSubscriptionsQuery, useRunBillingMutation } from './subscriptionsApi'

const TABS = [
  { label: 'All', value: '' },
  { label: 'Active', value: 'active' },
  { label: 'Cancelled', value: 'cancelled' },
]

const FINANCE_ROLES = ['finance_ops', 'admin']

export default function SubscriptionsListPage() {
  const [tab, setTab] = useState('')
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10))
  const membership = useSelector(selectActiveMembership)
  const canRunBilling = FINANCE_ROLES.includes(membership?.role?.code)

  const { data: subscriptions = [], isLoading } = useGetSubscriptionsQuery(
    tab ? { status: tab } : undefined,
  )
  const [runBilling, billingState] = useRunBillingMutation()

  const active = subscriptions.filter((item) => item.status === 'active')
  const recurringValue = active.reduce((sum, item) => sum + Number(item.cycle_amount), 0)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Subscriptions &amp; Billing</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Every recurring line on a confirmed order becomes a subscription with its own billing
            schedule. One-time charges stay on the order invoice.
          </p>
        </div>
        {canRunBilling && (
          <div className="text-right">
            <div className="flex items-center gap-2">
              {/* An "as at" date, because the next period is usually months away and a run
                  pinned to today would have nothing to do. */}
              <input
                type="date"
                value={asOf}
                onChange={(event) => setAsOf(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                aria-label="Bill as at date"
              />
              <button
                onClick={() => runBilling(asOf ? { as_of: asOf } : {})}
                disabled={billingState.isLoading}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                {billingState.isLoading ? 'Running…' : 'Run recurring billing'}
              </button>
            </div>
            {billingState.data && (
              <p className="mt-1.5 text-xs text-slate-500">
                {billingState.data.invoices_created > 0
                  ? `${billingState.data.invoices_created} invoice(s) raised as at ${billingState.data.as_of}.`
                  : `Nothing due as at ${billingState.data.as_of}.`}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Active subscriptions" value={active.length} />
        <SummaryCard label="Recurring value per cycle" value={formatCurrency(recurringValue)} />
        <SummaryCard
          label="Next billing date"
          value={
            active.length > 0
              ? active.map((item) => item.next_bill_date).sort()[0]
              : '—'
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-4 border-b border-slate-200">
        {TABS.map((item) => (
          <button
            key={item.label}
            onClick={() => setTab(item.value)}
            className={`-mb-px border-b-2 px-1 pb-2.5 text-sm transition ${
              tab === item.value
                ? 'border-brand-600 font-medium text-brand-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              {['Subscription', 'Customer', 'Plan / Cycle', 'Qty', 'Per cycle', 'Next bill', 'Status'].map(
                (heading, index) => (
                  <th
                    key={heading}
                    className={`px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 ${
                      index === 3 || index === 4 ? 'text-right' : 'text-left'
                    }`}
                  >
                    {heading}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading subscriptions…
                </td>
              </tr>
            )}
            {!isLoading && subscriptions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  Nothing here yet. A subscription appears when a quotation carrying a recurring
                  line is confirmed.
                </td>
              </tr>
            )}
            {subscriptions.map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="px-5 py-3">
                  <Link
                    to={`/subscriptions/${item.id}/billing`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {item.product_name}
                  </Link>
                  <span className="mt-0.5 block text-xs text-slate-400">
                    {item.quotation_number ?? 'no linked quotation'}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className="text-sm text-slate-900">{item.customer_name}</span>
                  <span className="mt-0.5 block">
                    <StatusPill value={item.customer_tier} label={item.customer_tier} />
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {item.plan_name}
                  <span className="mt-0.5 block text-xs text-slate-400">{item.cycle}</span>
                </td>
                <td className="px-5 py-3 text-right text-sm text-slate-600">
                  {parseFloat(item.qty)}
                </td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(item.cycle_amount)}
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {item.status === 'active' ? item.next_bill_date : '—'}
                </td>
                <td className="px-5 py-3">
                  <StatusPill value={item.status} label={item.status_label} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SummaryCard({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  )
}
