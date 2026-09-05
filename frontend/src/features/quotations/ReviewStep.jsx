import { useState } from 'react'
import { Link } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency, formatPct } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import NegotiationPanel from './NegotiationPanel'
import { useDeleteLineMutation, useUpdateLineMutation } from './quotationsApi'

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function DiscountCell({ quotationId, line, editable }) {
  const [value, setValue] = useState(String(parseFloat(line.discount_pct)))
  const [error, setError] = useState(null)
  const [updateLine, { isLoading }] = useUpdateLineMutation()

  async function commit() {
    const next = Number(value)
    if (Number.isNaN(next) || next === Number(line.discount_pct)) {
      setValue(String(parseFloat(line.discount_pct)))
      setError(null)
      return
    }
    try {
      await updateLine({ quotationId, lineId: line.id, discount_pct: next }).unwrap()
      setError(null)
    } catch (err) {
      // Reverting without saying why leaves the rep guessing — show the API's reason.
      const { formError, fieldErrors } = parseApiError(err)
      setError(fieldErrors.discount_pct ?? formError ?? 'Could not save')
      setValue(String(parseFloat(line.discount_pct)))
    }
  }

  if (!editable) return <span className="text-sm text-slate-600">{formatPct(line.discount_pct)}</span>

  return (
    <div className="inline-flex flex-col items-end">
      <div className="inline-flex items-center gap-1">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          disabled={isLoading}
          className={`w-16 rounded-md border px-2 py-1 text-right text-sm outline-none focus:ring-2 ${
            error
              ? 'border-red-400 focus:border-red-500 focus:ring-red-100'
              : 'border-slate-300 focus:border-brand-600 focus:ring-brand-100'
          }`}
        />
        <span className="text-sm text-slate-500">%</span>
      </div>
      {error && <span className="mt-1 max-w-[180px] text-right text-xs text-red-600">{error}</span>}
    </div>
  )
}

/** Where the deal actually stands — who is holding it, or why it came back. Without this
 *  the rep has a quotation page that says "Pending Approval" and nothing else. */
function GovernanceBanner({ quotation }) {
  const approval = quotation.active_approval
  const decision = quotation.last_decision

  if (quotation.status === 'pending_approval' && approval) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-amber-900">
              Waiting on {approval.current_stage_label ?? 'review'}
            </h2>
            <p className="mt-1 text-sm text-amber-800">
              Routing score {parseFloat(approval.risk_score_snapshot)} required{' '}
              {approval.required_level === 'manager_then_finance'
                ? 'Sales Manager then Finance'
                : 'Sales Manager'}
              . Editing any line re-scores the deal and restarts this approval from the first
              stage.
            </p>
            <p className="mt-1 text-xs text-amber-700">
              That score is the greater of the blended average (
              {parseFloat(quotation.blended_risk_score)}) and the worst single line (
              {parseFloat(quotation.max_single_overage)}), so one heavily discounted line
              cannot hide inside an otherwise-compliant quote.
            </p>
          </div>
          <Link
            to={`/approvals/${approval.id}`}
            className="whitespace-nowrap rounded-lg border border-amber-600 px-3.5 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
          >
            View approval
          </Link>
        </div>
      </div>
    )
  }

  if (quotation.status === 'rejected' && decision) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4">
        <h2 className="text-sm font-semibold text-red-900">
          Rejected by {decision.reviewer_name} ({decision.stage_label})
        </h2>
        {decision.reason && <p className="mt-1 text-sm text-red-800">“{decision.reason}”</p>}
        <p className="mt-2 text-sm text-red-800">
          A rejection is final — this quotation can no longer be edited or resubmitted. Start a
          new quotation for the customer.
        </p>
      </div>
    )
  }

  if (quotation.status === 'draft' && decision?.action === 'returned') {
    return (
      <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
        <h2 className="text-sm font-semibold text-orange-900">
          Returned by {decision.reviewer_name} ({decision.stage_label})
        </h2>
        {decision.reason && <p className="mt-1 text-sm text-orange-800">“{decision.reason}”</p>}
        <p className="mt-2 text-sm text-orange-800">
          Adjust the lines below and submit again — that opens a fresh approval cycle.
        </p>
      </div>
    )
  }

  if (quotation.status === 'negotiation') {
    const counter = [...(quotation.negotiation ?? [])]
      .reverse()
      .find((message) => message.message_type === 'counter_offer')
    return (
      <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
        <h2 className="text-sm font-semibold text-violet-900">Live with the customer</h2>
        <p className="mt-1 text-sm text-violet-800">
          {counter
            ? `${quotation.customer_name} counter-offered ${parseFloat(
                counter.counter_discount_pct,
              )}%${counter.line_label ? ` on ${counter.line_label}` : ' on the whole quote'}, and it cleared policy — the lines below already reflect it.`
            : `${quotation.customer_name} has the portal link open.`}{' '}
          A counter-offer that breaches a ceiling re-opens approval on its own; nobody has to
          resubmit it.
        </p>
      </div>
    )
  }

  if (quotation.status === 'confirmed') {
    return (
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
        <h2 className="text-sm font-semibold text-blue-900">Confirmed by the customer</h2>
        <p className="mt-1 text-sm text-blue-800">
          Accepted from the customer portal. Fulfillment and billing have been raised
          automatically.
        </p>
      </div>
    )
  }

  if (quotation.status === 'approved') {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
        <h2 className="text-sm font-semibold text-emerald-900">Approved</h2>
        <p className="mt-1 text-sm text-emerald-800">
          {decision
            ? `Signed off by ${decision.reviewer_name} (${decision.stage_label}).`
            : 'Within policy, so no approval was required.'}{' '}
          Approved quotations are locked from editing.
        </p>
      </div>
    )
  }

  return null
}

export default function ReviewStep({ quotation, editable, onBack, onSubmit, isSubmitting, submitError }) {
  const [deleteLine] = useDeleteLineMutation()
  const { formError } = parseApiError(submitError)
  const customer = quotation.customer_detail ?? {}
  const gross = quotation.lines.reduce((sum, l) => sum + Number(l.qty) * Number(l.unit_price), 0)
  const net = quotation.lines.reduce((sum, l) => sum + Number(l.line_total), 0)

  return (
    <div className="space-y-5">
      {formError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {formError}
        </div>
      )}

      <GovernanceBanner quotation={quotation} />

      <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <div className="space-y-5">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Customer Details</h2>
            <div className="mt-4 flex flex-wrap justify-between gap-6">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-sm font-semibold text-slate-600">
                  {(customer.name ?? '?').slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-slate-900">{customer.name}</p>
                    <StatusPill value={customer.tier} label={`${customer.tier} Tier`} />
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">
                    {customer.email}
                    {customer.location ? ` · ${customer.location}` : ''}
                  </p>
                </div>
              </div>
              <dl className="grid grid-cols-[auto_auto] gap-x-6 gap-y-1 text-sm">
                <dt className="text-slate-500">Quote Number</dt>
                <dd className="text-right font-medium text-slate-900">{quotation.number}</dd>
                <dt className="text-slate-500">Date</dt>
                <dd className="text-right text-slate-700">{formatDate(quotation.created_at)}</dd>
                <dt className="text-slate-500">Valid Till</dt>
                <dd className="text-right text-slate-700">{formatDate(quotation.valid_till)}</dd>
              </dl>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Products</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wide text-slate-500">Qty</th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Unit Price</th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Discount</th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Total</th>
                  {editable && <th className="px-5 py-3" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotation.lines.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                      No lines yet — go back and add products.
                    </td>
                  </tr>
                )}
                {quotation.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="px-5 py-3">
                      <p className="text-sm font-medium text-slate-900">{line.product_name}</p>
                      <p className="text-xs text-slate-500">
                        {line.product_category}
                        {line.line_type === 'recurring' ? ' · Recurring' : ''}
                      </p>
                    </td>
                    <td className="px-5 py-3 text-center text-sm text-slate-700">
                      {parseFloat(line.qty)}
                    </td>
                    <td className="px-5 py-3 text-right text-sm text-slate-700">
                      {formatCurrency(line.unit_price)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <DiscountCell quotationId={quotation.id} line={line} editable={editable} />
                    </td>
                    <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                      {formatCurrency(line.line_total)}
                    </td>
                    {editable && (
                      <td className="px-3 py-3 text-right">
                        <button
                          onClick={() =>
                            deleteLine({ quotationId: quotation.id, lineId: line.id })
                          }
                          className="text-xs text-slate-400 hover:text-red-600"
                          aria-label="Remove line"
                        >
                          Remove
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 bg-slate-50">
                <tr>
                  <td colSpan={editable ? 5 : 4} className="px-5 py-3 text-right text-sm text-slate-500">
                    Gross
                  </td>
                  <td className="px-5 py-3 text-right text-sm text-slate-600">
                    {formatCurrency(gross)}
                  </td>
                </tr>
                <tr>
                  <td colSpan={editable ? 5 : 4} className="px-5 py-3 text-right text-sm font-semibold text-slate-900">
                    Total Value
                  </td>
                  <td className="px-5 py-3 text-right text-base font-semibold text-slate-900">
                    {formatCurrency(net)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </section>

          <NegotiationPanel quotation={quotation} />
        </div>

        <aside className="space-y-5">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Quote Summary</h2>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Status</dt>
                <dd><StatusPill value={quotation.status} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Lines</dt>
                <dd className="text-slate-900">{quotation.lines.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Avg. discount</dt>
                <dd className="text-slate-900">{formatPct(quotation.average_discount_pct)}</dd>
              </div>
              {/* Headlines the same number the governance banner and the approvals
                  screens use — the routing score. The two inputs it is derived from sit
                  underneath so the figures can always be reconciled. */}
              <div className="flex justify-between">
                <dt className="text-slate-500">Routing score</dt>
                <dd className="font-medium text-slate-900">
                  {parseFloat(quotation.routing_score)}
                </dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-400">Blended average</dt>
                <dd className="text-slate-500">{parseFloat(quotation.blended_risk_score)}</dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-400">Worst single line</dt>
                <dd className="text-slate-500">{parseFloat(quotation.max_single_overage)}</dd>
              </div>
            </dl>
          </section>

          {/* Step 8 fills this in — the live upsell engine is not built yet. */}
          <section className="rounded-xl border border-dashed border-slate-300 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-400">Upsell & Cross-sell</h2>
            <p className="mt-2 text-xs text-slate-400">
              Recommendations appear here once the upsell engine lands (build step 8).
            </p>
          </section>
        </aside>
      </div>

      <div className="flex justify-end gap-2">
        {onBack && (
          <button
            onClick={onBack}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back
          </button>
        )}
        {editable && quotation.status !== 'pending_approval' && (
          <button
            onClick={onSubmit}
            disabled={isSubmitting || quotation.lines.length === 0}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {isSubmitting ? 'Submitting…' : 'Submit for Approval'}
          </button>
        )}
      </div>
    </div>
  )
}
