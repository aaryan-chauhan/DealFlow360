import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import StatusPill from '../../shared/ui/StatusPill'
import {
  useCancelSubscriptionMutation,
  useGetBillingDetailQuery,
  useGetSubscriptionPlansQuery,
  useModifySubscriptionMutation,
} from './subscriptionsApi'

const REFUND_LABELS = {
  full_refund: 'Full refund',
  prorated_refund: 'Prorated refund',
  no_refund: 'No refund',
}

export default function BillingDetailPage() {
  const { id } = useParams()
  const { data: subscription, isLoading } = useGetBillingDetailQuery(id)
  const [dialog, setDialog] = useState(null)

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading billing schedule…</p>
  }
  if (!subscription) {
    return <p className="text-sm text-slate-500">Subscription not found.</p>
  }

  const isActive = subscription.status === 'active'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/subscriptions" className="text-xs text-brand-600 hover:text-brand-700">
            ← Subscriptions
          </Link>
          <h1 className="mt-1 flex items-center gap-2.5 text-xl font-semibold text-slate-900">
            {subscription.product_name}
            <StatusPill value={subscription.status} label={subscription.status_label} />
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {subscription.customer_name} ·{' '}
            {subscription.quotation_number ? (
              <Link
                to={`/quotations/${subscription.quotation}`}
                className="text-brand-600 hover:text-brand-700"
              >
                {subscription.quotation_number}
              </Link>
            ) : (
              'migrated contract — no originating quotation'
            )}
          </p>
        </div>

        {isActive && (
          <div className="flex gap-2">
            {subscription.can_manage && (
              <button
                onClick={() => setDialog('modify')}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
              >
                Modify quantity / plan
              </button>
            )}
            {subscription.can_refund && (
              <button
                onClick={() => setDialog('cancel')}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
              >
                Cancel subscription
              </button>
            )}
          </div>
        )}
      </div>

      {!isActive && subscription.cancelled_at && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-600">
          Cancelled on {new Date(subscription.cancelled_at).toLocaleDateString()}
          {subscription.cancellation_reason && <> — “{subscription.cancellation_reason}”</>}. The{' '}
          <span className="font-medium">
            {REFUND_LABELS[subscription.plan_detail.refund_type]}
          </span>{' '}
          rule on {subscription.plan_name} was applied.
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <DetailsCard subscription={subscription} />
        <div className="space-y-5 lg:col-span-2">
          <BillingSchedule subscription={subscription} />
          <ProrationHistory subscription={subscription} />
          <CreditNotes subscription={subscription} />
          <OneTimeSiblings subscription={subscription} />
        </div>
      </div>

      {dialog === 'modify' && (
        <ModifyDialog subscription={subscription} onClose={() => setDialog(null)} />
      )}
      {dialog === 'cancel' && (
        <CancelDialog subscription={subscription} onClose={() => setDialog(null)} />
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */

function Row({ label, value, hint }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-right text-sm font-medium text-slate-900">
        {value}
        {hint && <span className="mt-0.5 block text-xs font-normal text-slate-400">{hint}</span>}
      </span>
    </div>
  )
}

function DetailsCard({ subscription }) {
  return (
    <div className="h-fit rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Subscription details</h2>
      <div className="mt-2 divide-y divide-slate-100">
        <Row label="Plan" value={subscription.plan_name} hint={subscription.cycle} />
        <Row label="Quantity" value={parseFloat(subscription.qty)} />
        <Row label="Unit price" value={formatCurrency(subscription.unit_price)} />
        <Row
          label="Per cycle"
          value={formatCurrency(subscription.cycle_amount)}
          hint="standard, before proration"
        />
        <Row label="Started" value={subscription.start_date} />
        <Row
          label="Next bill date"
          value={subscription.status === 'active' ? subscription.next_bill_date : '—'}
        />
        <Row label="Billed to date" value={formatCurrency(subscription.lifetime_billed)} />
        <Row label="Scheduled ahead" value={formatCurrency(subscription.scheduled_value)} />
        <Row
          label="On cancellation"
          value={REFUND_LABELS[subscription.plan_detail.refund_type]}
        />
        <Row
          label="Mid-cycle changes"
          value={subscription.plan_detail.proration_rule?.mode === 'none' ? 'Not prorated' : 'Prorated daily'}
        />
      </div>
      {subscription.owner_name && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">
          Deal owner: {subscription.owner_name}
        </p>
      )}
    </div>
  )
}

function BillingSchedule({ subscription }) {
  const cycles = subscription.billing_cycles
  const currentId = subscription.current_cycle?.id

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Upcoming billing schedule</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Each period is a real billing cycle row. A billed period is never rewritten — a mid-cycle
        change lands on the next unbilled one.
      </p>

      {cycles.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No periods scheduled.</p>
      ) : (
        <ol className="mt-4 space-y-0">
          {cycles.map((cycle, index) => {
            const isCurrent = cycle.id === currentId
            const isProrated = cycle.amount !== cycle.standard_amount && !cycle.is_billed
            return (
              <li key={cycle.id} className="relative flex gap-4 pb-5 last:pb-0">
                {index < cycles.length - 1 && (
                  <span className="absolute left-[7px] top-4 h-full w-px bg-slate-200" aria-hidden />
                )}
                <span
                  className={`relative z-10 mt-1 h-3.5 w-3.5 shrink-0 rounded-full border-2 ${
                    cycle.is_billed
                      ? 'border-emerald-500 bg-emerald-500'
                      : isCurrent
                        ? 'border-brand-600 bg-white'
                        : 'border-slate-300 bg-white'
                  }`}
                  aria-hidden
                />
                <div className="flex flex-1 flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-4 last:border-0 last:pb-0">
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {cycle.period_start} → {cycle.period_end}
                      {isCurrent && (
                        <span className="ml-2 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                          Current
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {cycle.days_in_cycle} days
                      {cycle.invoice_number && (
                        <>
                          {' · '}
                          <Link
                            to={`/invoices/${cycle.invoice_id}`}
                            className="text-brand-600 hover:text-brand-700"
                          >
                            {cycle.invoice_number}
                          </Link>
                        </>
                      )}
                    </p>
                    {isProrated && (
                      <p className="mt-1 text-xs text-amber-700">
                        Adjusted from {formatCurrency(cycle.standard_amount)} by a proration event.
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900">
                      {formatCurrency(cycle.amount)}
                    </p>
                    <span
                      className={`mt-0.5 inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        cycle.is_billed
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {cycle.is_billed ? 'Billed' : 'Scheduled'}
                    </span>
                  </div>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

function ProrationHistory({ subscription }) {
  if (subscription.proration_events.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Proration &amp; change history</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Why a period differs from the standard amount.
      </p>
      <div className="mt-3 space-y-3">
        {subscription.proration_events.map((event) => (
          <div key={event.id} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-sm font-medium text-slate-900">
                {event.change_type_label}
                <span className="ml-2 text-xs font-normal text-slate-500">
                  effective {event.effective_date}
                </span>
              </span>
              <span
                className={`text-sm font-semibold ${
                  Number(event.delta_amount) < 0 ? 'text-emerald-700' : 'text-slate-900'
                }`}
              >
                {Number(event.delta_amount) >= 0 ? '+' : ''}
                {formatCurrency(event.delta_amount)}
              </span>
            </div>
            {event.details?.formula && (
              <p className="mt-1 font-mono text-xs text-slate-600">{event.details.formula}</p>
            )}
            {event.details?.applied_to_period && (
              <p className="mt-1 text-xs text-slate-500">
                Applied to the period {event.details.applied_to_period}.
              </p>
            )}
            {event.details?.reason && (
              <p className="mt-1 text-xs text-slate-500">“{event.details.reason}”</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function CreditNotes({ subscription }) {
  if (subscription.credit_notes.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Credit notes</h2>
      <div className="mt-3 space-y-2">
        {subscription.credit_notes.map((note) => (
          <div
            key={note.id}
            className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5"
          >
            <div>
              <p className="text-sm font-medium text-emerald-900">{note.reason}</p>
              <p className="mt-0.5 text-xs text-emerald-700">
                {note.invoice_number ? (
                  <>
                    Against{' '}
                    <Link to={`/invoices/${note.invoice_id}`} className="underline">
                      {note.invoice_number}
                    </Link>
                  </>
                ) : (
                  'Raised directly against this subscription — no invoice involved'
                )}
              </p>
            </div>
            <span className="text-sm font-semibold text-emerald-900">
              {formatCurrency(note.amount)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function OneTimeSiblings({ subscription }) {
  if (subscription.order_one_time_lines.length === 0) return null
  const invoice = subscription.order_one_time_lines[0]

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
      <h2 className="text-sm font-semibold text-slate-900">
        Also on this order — one-time items
      </h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Billed once on{' '}
        <Link to={`/invoices/${invoice.invoice_id}`} className="text-brand-600 hover:text-brand-700">
          {invoice.invoice_number}
        </Link>
        . Shown here for context only — these never enter the recurring schedule above.
      </p>
      <table className="mt-3 w-full">
        <tbody className="divide-y divide-slate-200">
          {subscription.order_one_time_lines.map((line) => (
            <tr key={line.id}>
              <td className="py-2 text-sm text-slate-700">{line.description}</td>
              <td className="py-2 text-right text-xs text-slate-500">
                {parseFloat(line.qty)} × {formatCurrency(line.unit_price)}
              </td>
              <td className="py-2 text-right text-sm font-medium text-slate-900">
                {formatCurrency(line.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* -------------------------------------------------------------------------- */

function ModifyDialog({ subscription, onClose }) {
  const [qty, setQty] = useState(String(parseFloat(subscription.qty)))
  const [planId, setPlanId] = useState(subscription.plan)
  const [reason, setReason] = useState('')
  const { data: plans = [] } = useGetSubscriptionPlansQuery()
  const [modify, state] = useModifySubscriptionMutation()
  const { formError, fieldErrors } = parseApiError(state.error)

  const cycle = subscription.current_cycle
  const daysRemaining = cycle
    ? Math.max(
        0,
        Math.min(
          cycle.days_in_cycle,
          Math.round((new Date(cycle.period_end) - new Date()) / 86400000),
        ),
      )
    : 0
  // Mirrors §7.3.2 so the rep sees the number before committing. The server recomputes it
  // authoritatively — this is a preview, never the value that gets stored.
  const preview =
    cycle && qty !== ''
      ? (Number(qty) - Number(subscription.qty)) *
        Number(subscription.unit_price) *
        (daysRemaining / cycle.days_in_cycle)
      : 0

  async function submit(event) {
    event.preventDefault()
    const body = { id: subscription.id, reason }
    if (Number(qty) !== Number(subscription.qty)) body.new_qty = qty
    if (planId !== subscription.plan) body.new_plan = planId
    try {
      await modify(body).unwrap()
      onClose()
    } catch {
      /* surfaced below */
    }
  }

  return (
    <Modal
      title="Modify subscription"
      subtitle="A mid-cycle change is prorated over the days left in the current period."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Quantity</span>
          <input
            type="number"
            min="0.01"
            step="1"
            value={qty}
            onChange={(event) => setQty(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
          {fieldErrors.new_qty && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.new_qty}</span>
          )}
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Plan</span>
          <select
            value={planId}
            onChange={(event) => setPlanId(event.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          >
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} ({plan.cycle})
              </option>
            ))}
          </select>
          {fieldErrors.new_plan && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.new_plan}</span>
          )}
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Reason</span>
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="e.g. Customer added 4 more sites"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
        </label>

        {cycle && (
          <div className="rounded-lg bg-slate-50 px-4 py-3 text-xs text-slate-600">
            <p className="font-medium text-slate-700">Estimated proration</p>
            <p className="mt-1 font-mono">
              ({qty || 0} − {parseFloat(subscription.qty)}) × {subscription.unit_price} × (
              {daysRemaining}/{cycle.days_in_cycle}) ={' '}
              <span className="font-semibold text-slate-900">{formatCurrency(preview)}</span>
            </p>
            <p className="mt-1 text-slate-500">
              {cycle.is_billed
                ? 'The current period is already billed, so this lands on the next scheduled period.'
                : 'This adjusts the current, not-yet-billed period.'}
            </p>
          </div>
        )}

        {formError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={state.isLoading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {state.isLoading ? 'Applying…' : 'Apply change'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function CancelDialog({ subscription, onClose }) {
  const [reason, setReason] = useState('')
  const [cancel, state] = useCancelSubscriptionMutation()
  const { formError, fieldErrors } = parseApiError(state.error)
  const refundType = subscription.plan_detail.refund_type

  async function submit(event) {
    event.preventDefault()
    try {
      await cancel({ id: subscription.id, reason }).unwrap()
      onClose()
    } catch {
      /* surfaced below */
    }
  }

  return (
    <Modal
      title="Cancel subscription"
      subtitle={`${subscription.plan_name} applies the ${REFUND_LABELS[refundType]} rule.`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="rounded-lg bg-slate-50 px-4 py-3 text-xs text-slate-600">
          <p className="font-medium text-slate-700">What will happen</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-4">
            <li>
              {refundType === 'no_refund'
                ? 'No credit note — this plan refunds nothing on cancellation.'
                : refundType === 'full_refund'
                  ? 'A credit note for the full current-period charge.'
                  : 'A credit note for the unserved part of the current period.'}
            </li>
            <li>Every scheduled, not-yet-billed period is dropped so nothing bills again.</li>
            <li>Already-issued invoices are left untouched.</li>
          </ul>
        </div>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Reason <span className="text-red-500">*</span>
          </span>
          <textarea
            required
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Required — logged to the audit trail with your name and the timestamp."
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
          {fieldErrors.reason && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.reason}</span>
          )}
        </label>

        {formError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Keep it
          </button>
          <button
            type="submit"
            disabled={state.isLoading}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
          >
            {state.isLoading ? 'Cancelling…' : 'Cancel subscription'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
