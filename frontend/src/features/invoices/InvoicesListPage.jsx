import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetInvoicesQuery } from './invoicesApi'

const TABS = [
  { label: 'All', params: undefined },
  { label: 'Orders', params: { type: 'one_time' } },
  { label: 'Recurring runs', params: { type: 'recurring' } },
  { label: 'Unpaid', params: { status: 'issued,partially_paid' } },
  { label: 'Paid', params: { status: 'paid' } },
]

export default function InvoicesListPage() {
  const [tab, setTab] = useState(0)
  const { data: invoices = [], isLoading } = useGetInvoicesQuery(TABS[tab].params)

  const outstanding = invoices.reduce((sum, item) => sum + Number(item.balance_due), 0)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Invoices</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          An order raises one invoice that can carry both one-time and recurring charges — held in
          separate line pools. The billing run raises its own recurring-only invoices.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Invoices" value={invoices.length} />
        <SummaryCard label="Outstanding" value={formatCurrency(outstanding)} />
        <SummaryCard
          label="Mixed (one-time + recurring)"
          value={invoices.filter((item) => item.is_mixed).length}
        />
      </div>

      <div className="flex flex-wrap items-center gap-4 border-b border-slate-200">
        {TABS.map((item, index) => (
          <button
            key={item.label}
            onClick={() => setTab(index)}
            className={`-mb-px border-b-2 px-1 pb-2.5 text-sm transition ${
              tab === index
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
              {['Invoice', 'Customer', 'Contents', 'Issued', 'Due', 'Total', 'Balance', 'Status'].map(
                (heading, index) => (
                  <th
                    key={heading}
                    className={`px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 ${
                      index === 5 || index === 6 ? 'text-right' : 'text-left'
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
                <td colSpan={8} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading invoices…
                </td>
              </tr>
            )}
            {!isLoading && invoices.length === 0 && (
              <tr>
                <td colSpan={8} className="px-5 py-10 text-center text-sm text-slate-500">
                  No invoices here. One is raised when a quotation is confirmed, and by each
                  recurring billing run.
                </td>
              </tr>
            )}
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="hover:bg-slate-50">
                <td className="px-5 py-3">
                  <Link
                    to={`/invoices/${invoice.id}`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {invoice.invoice_number}
                  </Link>
                  {invoice.quotation_number && (
                    <span className="mt-0.5 block text-xs text-slate-400">
                      {invoice.quotation_number}
                    </span>
                  )}
                </td>
                <td className="px-5 py-3 text-sm text-slate-900">{invoice.customer_name}</td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1">
                    {invoice.has_one_time && (
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                        One-time
                      </span>
                    )}
                    {invoice.has_recurring && (
                      <span className="rounded-md bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700">
                        Recurring
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">{invoice.issue_date}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{invoice.due_date ?? '—'}</td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(invoice.total_amount)}
                </td>
                <td className="px-5 py-3 text-right text-sm text-slate-600">
                  {formatCurrency(invoice.balance_due)}
                </td>
                <td className="px-5 py-3">
                  <StatusPill value={invoice.status} label={invoice.status_label} />
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
