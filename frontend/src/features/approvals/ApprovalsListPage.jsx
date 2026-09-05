import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetApprovalsQuery } from './approvalsApi'

const TABS = [
  { label: 'Waiting on me', value: 'mine' },
  { label: 'Pending', value: 'pending' },
  { label: 'Approved', value: 'approved' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'All', value: '' },
]

const STAGE_LABEL = { manager: 'Sales Manager', finance: 'Finance / Ops' }

export default function ApprovalsListPage() {
  const [tab, setTab] = useState('pending')
  // "Waiting on me" is the pending list narrowed to the steps this viewer's role can
  // actually action — the server already decides that per row via can_act.
  const { data: rows = [], isLoading } = useGetApprovalsQuery(
    tab && tab !== 'mine' ? { status: tab } : tab === 'mine' ? { status: 'pending' } : undefined,
  )
  const approvals = tab === 'mine' ? rows.filter((request) => request.can_act) : rows

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Approvals</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Quotations the risk engine routed for review. You can only act on the stage that matches
          your role.
        </p>
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
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Requested By</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Value</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Risk</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Waiting On</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading approvals…
                </td>
              </tr>
            )}
            {!isLoading && approvals.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  {tab === 'mine'
                    ? 'Nothing is waiting on you right now. A request appears here once the chain reaches your stage.'
                    : 'Nothing waiting here.'}
                </td>
              </tr>
            )}
            {approvals.map((request) => (
              <tr key={request.id} className="hover:bg-slate-50">
                <td className="px-5 py-3">
                  <Link
                    to={`/approvals/${request.id}`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {request.quotation_number}
                  </Link>
                </td>
                <td className="px-5 py-3 text-sm text-slate-900">{request.customer_name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{request.owner_name}</td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(request.total_value)}
                </td>
                <td className="px-5 py-3 text-right text-sm font-medium text-amber-700">
                  {parseFloat(request.risk_score_snapshot)}
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {request.current_stage ? STAGE_LABEL[request.current_stage] : '—'}
                  {request.can_act && (
                    <span className="ml-2 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                      You
                    </span>
                  )}
                </td>
                <td className="px-5 py-3">
                  <StatusPill value={request.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
