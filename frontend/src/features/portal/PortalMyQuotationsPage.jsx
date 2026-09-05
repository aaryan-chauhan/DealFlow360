import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { useGetMyQuotationsQuery, useOpenQuotationMutation } from './portalApi'

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})
const money = (value) => currency.format(Number(value ?? 0))

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

const STATUS_LABELS = {
  pending_approval: 'Pending Review',
  approved: 'Ready for You',
  negotiation: 'Under Negotiation',
  confirmed: 'Confirmed',
}

/** "My Quotations" (§1, §9) — the list a customer sees after logging in, as opposed to
 *  the single quotation a rep-sent magic link opens directly. Clicking a row mints an
 *  ordinary single-quotation session behind the scenes and lands on the exact same
 *  negotiation screen that link would have opened. */
export default function PortalMyQuotationsPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { data, isLoading, isError } = useGetMyQuotationsQuery(token)
  const [openQuotation] = useOpenQuotationMutation()
  const [openingId, setOpeningId] = useState(null)

  async function handleOpen(quotationId) {
    setOpeningId(quotationId)
    try {
      const result = await openQuotation({ token, quotationId }).unwrap()
      navigate(`/portal/quotations/${result.token}`)
    } catch {
      setOpeningId(null)
    }
  }

  if (isError) {
    return (
      <div className="mx-auto mt-24 max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
        <h1 className="text-lg font-semibold text-slate-900">Your session has expired</h1>
        <p className="mt-2 text-sm text-slate-600">Please log in again.</p>
        <a href="/portal" className="mt-4 inline-block text-sm font-semibold text-brand-600 hover:underline">
          Back to login
        </a>
      </div>
    )
  }

  const quotations = data?.quotations || []

  return (
    <div className="mx-auto mt-10 max-w-3xl px-4">
      <h1 className="text-lg font-semibold text-slate-900">
        {data?.customer ? `Welcome, ${data.customer.name}` : 'My Quotations'}
      </h1>
      <p className="mt-1 text-sm text-slate-500">Every quotation shared with you, across every deal.</p>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-slate-500">Loading…</p>
        ) : quotations.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">
            No quotations have been shared with you yet.
          </p>
        ) : (
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Quote</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">From</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Value</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Updated</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {quotations.map((q) => (
                <tr key={q.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 text-sm font-medium text-slate-900">{q.number}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{q.company_name}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">
                    {STATUS_LABELS[q.status] || q.status}
                  </td>
                  <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                    {money(q.total_value)}
                  </td>
                  <td className="px-5 py-3 text-right text-sm text-slate-500">
                    {formatDate(q.updated_at)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleOpen(q.id)}
                      disabled={openingId === q.id}
                      className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      {openingId === q.id ? 'Opening…' : 'Open'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
