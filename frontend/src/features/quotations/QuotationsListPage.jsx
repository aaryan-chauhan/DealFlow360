import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetQuotationsQuery } from './quotationsApi'

const TABS = [
  { label: 'All', value: '' },
  { label: 'Draft', value: 'draft' },
  { label: 'Pending Approval', value: 'pending_approval' },
  { label: 'Approved', value: 'approved' },
  { label: 'Rejected', value: 'rejected' },
]

export default function QuotationsListPage() {
  const [tab, setTab] = useState('')
  const { data: quotations = [], isLoading } = useGetQuotationsQuery(
    tab ? { status: tab } : undefined,
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Quotations</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Reps see their own pipeline; managers, finance and admins see the whole company.
          </p>
        </div>
        <Link
          to="/quotations/new"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          + New Quotation
        </Link>
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
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Quote</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Customer</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Owner</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Value</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Risk</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading quotations…
                </td>
              </tr>
            )}
            {!isLoading && quotations.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                  Nothing here yet.
                </td>
              </tr>
            )}
            {quotations.map((quotation) => (
              <tr key={quotation.id} className="hover:bg-slate-50">
                <td className="px-5 py-3">
                  <Link
                    to={`/quotations/${quotation.id}`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {quotation.number}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {quotation.line_count} line{quotation.line_count === 1 ? '' : 's'}
                  </p>
                </td>
                <td className="px-5 py-3">
                  <p className="text-sm text-slate-900">{quotation.customer_name}</p>
                  <p className="text-xs text-slate-500">{quotation.customer_tier}</p>
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">{quotation.owner_name}</td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(quotation.total_value)}
                </td>
                <td className="px-5 py-3 text-right text-sm text-slate-600">
                  {parseFloat(quotation.blended_risk_score)}
                </td>
                <td className="px-5 py-3">
                  <StatusPill value={quotation.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
