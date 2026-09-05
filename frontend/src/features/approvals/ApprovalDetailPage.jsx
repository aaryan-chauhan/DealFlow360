import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency, formatPct } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import StatusPill from '../../shared/ui/StatusPill'
import {
  useApproveRequestMutation,
  useGetApprovalQuery,
  useRejectRequestMutation,
  useReturnRequestMutation,
} from './approvalsApi'

const STAGE_TONE = {
  approved: 'border-emerald-500 bg-emerald-500 text-white',
  rejected: 'border-red-500 bg-red-500 text-white',
  returned: 'border-orange-500 bg-orange-500 text-white',
  pending: 'border-slate-300 bg-white text-slate-400',
}

function formatDateTime(value) {
  if (!value) return null
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ChainStep({ index, title, subtitle, action, actedAt }) {
  return (
    <li className="flex gap-3">
      <span
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
          STAGE_TONE[action] ?? STAGE_TONE.pending
        }`}
      >
        {action === 'approved' ? '✓' : action === 'rejected' ? '✕' : index}
      </span>
      <div className="flex-1 border-b border-slate-100 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-slate-900">{title}</p>
          <StatusPill value={action} />
        </div>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        {actedAt && <p className="mt-0.5 text-xs text-slate-400">{formatDateTime(actedAt)}</p>}
      </div>
    </li>
  )
}

function ReasonModal({ title, confirmLabel, tone, onClose, onConfirm, isLoading, error }) {
  const [reason, setReason] = useState('')
  const { formError, fieldErrors } = parseApiError(error)

  return (
    <Modal title={title} subtitle="A reason is mandatory and is written to the audit log." onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          onConfirm(reason)
        }}
      >
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Reason</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            required
            placeholder="Explain the decision for the audit trail…"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
          {fieldErrors.reason && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.reason}</span>
          )}
        </label>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading || !reason.trim()}
            className={`rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 ${
              tone === 'danger' ? 'bg-red-600 hover:bg-red-700' : 'bg-orange-500 hover:bg-orange-600'
            }`}
          >
            {isLoading ? 'Saving…' : confirmLabel}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function ApprovalDetailPage() {
  const { id } = useParams()
  const { data, isLoading } = useGetApprovalQuery(id)
  const [approve, approveState] = useApproveRequestMutation()
  const [reject, rejectState] = useRejectRequestMutation()
  const [returnToRep, returnState] = useReturnRequestMutation()
  const [modal, setModal] = useState(null)

  if (isLoading) return <p className="text-sm text-slate-500">Loading approval…</p>
  if (!data) return <p className="text-sm text-slate-500">Approval not found.</p>

  const quotation = data.quotation_detail
  const canAct = data.can_act
  const finalAction =
    data.status === 'approved' ? 'approved' : data.status === 'rejected' ? 'rejected' : 'pending'
  const { formError: approveError } = parseApiError(approveState.error)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            Approval Details – {data.quotation_number}
          </h1>
          <StatusPill value={data.status} />
        </div>
        <Link to="/approvals" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          All approvals
        </Link>
      </div>

      {approveError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {approveError}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">Approval Chain</h2>
          <ol className="mt-4 space-y-3">
            {data.steps.map((step, index) => (
              <ChainStep
                key={step.id}
                index={step.sequence}
                title={step.stage_label}
                subtitle={
                  step.reviewer_name
                    ? `${step.reviewer_name}${step.reason ? ` — “${step.reason}”` : ''}`
                    : index === 0 || data.steps[index - 1].action === 'approved'
                      ? 'Awaiting action'
                      : 'Not yet reached'
                }
                action={step.action}
                actedAt={step.acted_at}
              />
            ))}
            <ChainStep
              index={data.steps.length + 1}
              title="Final Approval"
              subtitle="System"
              action={finalAction}
            />
          </ol>

          <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-200 pt-4">
            <button
              onClick={() => approve({ id })}
              disabled={!canAct || approveState.isLoading}
              className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {approveState.isLoading ? 'Approving…' : 'Approve'}
            </button>
            <button
              onClick={() => setModal('reject')}
              disabled={!canAct}
              className="rounded-lg bg-red-600 px-5 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject
            </button>
            <button
              onClick={() => setModal('return')}
              disabled={!canAct}
              className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Return to rep
            </button>
          </div>
          {!canAct && (
            <p className="mt-2 text-xs text-slate-500">
              {data.status !== 'pending'
                ? 'This request is closed.'
                : `Only the ${data.current_stage === 'finance' ? 'Finance / Ops' : 'Sales Manager'} reviewer can act on the current step — and never the quote's own owner.`}
            </p>
          )}
        </section>

        <aside className="space-y-5">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Quote Summary</h2>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Customer</dt>
                <dd className="text-right font-medium text-slate-900">{data.customer_name}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Total Value</dt>
                <dd className="text-right font-medium text-slate-900">
                  {formatCurrency(data.total_value)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Avg. Discount</dt>
                <dd className="text-right text-slate-900">
                  {formatPct(quotation.average_discount_pct)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Risk Score</dt>
                <dd className="text-right font-medium text-amber-700">
                  {parseFloat(data.risk_score_snapshot)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Requested By</dt>
                <dd className="text-right text-slate-900">{data.owner_name}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Requested On</dt>
                <dd className="text-right text-slate-700">{formatDateTime(data.created_at)}</dd>
              </div>
            </dl>
            <Link
              to={`/quotations/${data.quotation}`}
              className="mt-4 block rounded-lg border border-slate-300 py-2 text-center text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              View full quotation
            </Link>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Line Items</h2>
            <ul className="mt-3 space-y-2">
              {quotation.lines.map((line) => (
                <li key={line.id} className="flex justify-between gap-3 text-sm">
                  <span className="text-slate-700">
                    {line.product_name}
                    <span className="text-slate-400"> ×{parseFloat(line.qty)}</span>
                  </span>
                  <span className="whitespace-nowrap text-slate-900">
                    {formatCurrency(line.line_total)}
                    <span className="ml-1 text-xs text-amber-600">
                      −{parseFloat(line.discount_pct)}%
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900">Audit Log</h2>
        <ul className="mt-3 divide-y divide-slate-100">
          {data.audit.length === 0 && (
            <li className="py-3 text-sm text-slate-500">No entries yet.</li>
          )}
          {data.audit.map((entry) => (
            <li key={entry.id} className="flex flex-wrap justify-between gap-2 py-2.5">
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {entry.action.replaceAll('_', ' ')}
                </p>
                {entry.reason && <p className="text-xs text-slate-500">{entry.reason}</p>}
              </div>
              <p className="text-xs text-slate-400">
                {entry.user} · {formatDateTime(entry.created_at)}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {modal === 'reject' && (
        <ReasonModal
          title="Reject quotation"
          confirmLabel="Reject"
          tone="danger"
          isLoading={rejectState.isLoading}
          error={rejectState.error}
          onClose={() => setModal(null)}
          onConfirm={async (reason) => {
            try {
              await reject({ id, reason }).unwrap()
              setModal(null)
            } catch {
              /* surfaced in the modal */
            }
          }}
        />
      )}
      {modal === 'return' && (
        <ReasonModal
          title="Return to rep"
          confirmLabel="Return"
          tone="warning"
          isLoading={returnState.isLoading}
          error={returnState.error}
          onClose={() => setModal(null)}
          onConfirm={async (reason) => {
            try {
              await returnToRep({ id, reason }).unwrap()
              setModal(null)
            } catch {
              /* surfaced in the modal */
            }
          }}
        />
      )}
    </div>
  )
}
