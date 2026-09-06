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

// The Kanban stages a deal actually moves through (spec B1/B2) — Rejected is appended so
// a quote never disappears from the board entirely once it lands there.
const PIPELINE_COLUMNS = [
  { label: 'Draft', value: 'draft', tone: 'border-t-slate-400' },
  { label: 'Pending Approval', value: 'pending_approval', tone: 'border-t-amber-400' },
  { label: 'Approved', value: 'approved', tone: 'border-t-emerald-400' },
  { label: 'Negotiation', value: 'negotiation', tone: 'border-t-violet-400' },
  { label: 'Confirmed', value: 'confirmed', tone: 'border-t-blue-400' },
  { label: 'Rejected', value: 'rejected', tone: 'border-t-red-400' },
]

function QuotationCard({ quotation }) {
  return (
    <Link
      to={`/quotations/${quotation.id}`}
      className="block rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="truncate text-sm font-semibold text-slate-900">{quotation.customer_name}</p>
        <span className="shrink-0 whitespace-nowrap text-xs text-slate-400">{quotation.number}</span>
      </div>
      <p className="mt-1 text-base font-semibold text-slate-900">
        {formatCurrency(quotation.total_value)}
      </p>
      <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-slate-100 pt-2.5">
        <span className="truncate text-xs text-slate-500">{quotation.owner_name}</span>
        {Number(quotation.routing_score) > 0 && (
          <span className="whitespace-nowrap rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
            Risk {parseFloat(quotation.routing_score)}
          </span>
        )}
      </div>
    </Link>
  )
}

function PipelineBoard({ quotations, isLoading }) {
  if (isLoading) {
    return <p className="px-1 py-10 text-center text-sm text-slate-500">Loading pipeline…</p>
  }

  const byStatus = {}
  for (const quotation of quotations) {
    ;(byStatus[quotation.status] ??= []).push(quotation)
  }

  return (
    // A CSS grid with equal fr columns fits all six stages within the viewport width —
    // never a page-wide horizontal scrollbar, unlike a flex row of fixed-width columns
    // that only ever grows. Each column gets the *same* explicit height regardless of
    // how many cards it holds, so columns never look uneven; a column with more cards
    // than fits just scrolls internally.
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {PIPELINE_COLUMNS.map((column) => {
        const items = byStatus[column.value] ?? []
        return (
          <div key={column.value} className="flex min-w-0 flex-col">
            <div className={`rounded-t-xl border-t-4 bg-slate-50 px-3 py-2.5 ${column.tone}`}>
              <div className="flex items-center justify-between gap-2">
                <h3 className="truncate text-sm font-semibold text-slate-900">{column.label}</h3>
                <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
                  {items.length}
                </span>
              </div>
            </div>
            <div className="h-[560px] space-y-2.5 overflow-y-auto rounded-b-xl border border-t-0 border-slate-200 bg-slate-50/60 p-2.5">
              {items.length === 0 ? (
                <p className="px-1 py-6 text-center text-xs text-slate-400">Nothing here.</p>
              ) : (
                items.map((quotation) => (
                  <QuotationCard key={quotation.id} quotation={quotation} />
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function QuotationsListPage() {
  const [view, setView] = useState('pipeline')
  const [tab, setTab] = useState('')
  // The Kanban board needs every status on screen at once to lay out its columns, so it
  // always fetches unfiltered — the status tabs only narrow the table view.
  const { data: allQuotations = [], isLoading: pipelineLoading } = useGetQuotationsQuery(
    undefined,
    { skip: view !== 'pipeline' },
  )
  const { data: quotations = [], isLoading } = useGetQuotationsQuery(
    tab ? { status: tab } : undefined,
    { skip: view !== 'list' },
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
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            <button
              onClick={() => setView('pipeline')}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                view === 'pipeline' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              Pipeline
            </button>
            <button
              onClick={() => setView('list')}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                view === 'list' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              List
            </button>
          </div>
          <Link
            to="/quotations/new"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            + New Quotation
          </Link>
        </div>
      </div>

      {view === 'pipeline' && <PipelineBoard quotations={allQuotations} isLoading={pipelineLoading} />}

      {view === 'list' && (
      <>
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
                  {parseFloat(quotation.routing_score)}
                </td>
                <td className="px-5 py-3">
                  <StatusPill value={quotation.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </>
      )}
    </div>
  )
}
