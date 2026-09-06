import { useState } from 'react'
import { useSelector } from 'react-redux'
import { Link, useParams } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetInvoiceQuery, useIssueCreditNoteMutation, useRecordPaymentMutation } from './invoicesApi'

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  `${window.location.protocol}//${window.location.hostname}:8000/api`

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const { data: invoice, isLoading } = useGetInvoiceQuery(id)
  const [paying, setPaying] = useState(false)
  const [crediting, setCrediting] = useState(false)

  if (isLoading) return <p className="text-sm text-slate-500">Loading invoice…</p>
  if (!invoice) return <p className="text-sm text-slate-500">Invoice not found.</p>

  const settled = Number(invoice.balance_due) <= 0

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/invoices" className="text-xs text-brand-600 hover:text-brand-700">
            ← Invoices
          </Link>
          <h1 className="mt-1 flex items-center gap-2.5 text-xl font-semibold text-slate-900">
            {invoice.invoice_number}
            <StatusPill value={invoice.status} label={invoice.status_label} />
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {invoice.customer_name} · issued {invoice.issue_date} · due {invoice.due_date ?? '—'}
            {invoice.quotation_number && (
              <>
                {' · '}
                <Link
                  to={`/quotations/${invoice.quotation}`}
                  className="text-brand-600 hover:text-brand-700"
                >
                  {invoice.quotation_number}
                </Link>
              </>
            )}
          </p>
        </div>

        <div className="flex gap-2">
          <DownloadSummaryButton invoice={invoice} />
          {invoice.can_issue_credit_note && !settled && (
            <button
              onClick={() => setCrediting(true)}
              className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
            >
              Issue credit note
            </button>
          )}
          {invoice.can_record_payment && !settled && (
            <button
              onClick={() => setPaying(true)}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Record payment
            </button>
          )}
        </div>
      </div>

      {invoice.is_mixed && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 px-5 py-3 text-sm text-violet-900">
          This order carries <span className="font-medium">both</span> one-time and recurring
          charges. They are held as separate invoice lines — a one-time line points at a product, a
          recurring line at a subscription — and are never merged or totalled together.
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <LineSection
            title="One-time items"
            caption="Billed once on this order."
            accent="slate"
            lines={invoice.one_time_lines}
            subtotal={invoice.one_time_subtotal}
          />
          <LineSection
            title="Recurring items"
            caption="One billing period each. Future periods bill on their own schedule."
            accent="violet"
            lines={invoice.recurring_lines}
            subtotal={invoice.recurring_subtotal}
          />
        </div>

        <div className="space-y-5">
          <TotalsCard invoice={invoice} />
          <PaymentsCard invoice={invoice} />
        </div>
      </div>

      {paying && <PaymentDialog invoice={invoice} onClose={() => setPaying(false)} />}
      {crediting && <CreditNoteDialog invoice={invoice} onClose={() => setCrediting(false)} />}
    </div>
  )
}

/* -------------------------------------------------------------------------- */

/**
 * The summary endpoint sits behind the same JWT gate as everything else, so a plain
 * `<a href>` would hit it unauthenticated and 401. Fetch it with the token, then hand the
 * browser a blob to save.
 */
function DownloadSummaryButton({ invoice }) {
  const token = useSelector((state) => state.auth.access)
  const [busy, setBusy] = useState(false)

  async function download() {
    setBusy(true)
    try {
      const response = await fetch(
        `${apiBaseUrl}/invoices/${invoice.id}/download-summary`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!response.ok) throw new Error(response.statusText)
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${invoice.invoice_number}.txt`
      anchor.click()
      URL.revokeObjectURL(url)
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      onClick={download}
      disabled={busy}
      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
    >
      {busy ? 'Preparing…' : 'Download summary'}
    </button>
  )
}

const ACCENTS = {
  slate: {
    border: 'border-slate-200',
    head: 'bg-slate-50',
    dot: 'bg-slate-400',
    subtotal: 'text-slate-900',
  },
  violet: {
    border: 'border-violet-200',
    head: 'bg-violet-50',
    dot: 'bg-violet-500',
    subtotal: 'text-violet-900',
  },
}

/**
 * One pool of invoice lines. Rendered as its own bordered card with its own subtotal —
 * never as a section header inside a shared table — so the structural separation between
 * one-time and recurring charges is visible, not just implied by a column.
 */
function LineSection({ title, caption, accent, lines, subtotal }) {
  const tone = ACCENTS[accent]

  return (
    <div className={`overflow-hidden rounded-xl border bg-white ${tone.border}`}>
      <div className={`flex items-baseline justify-between gap-3 border-b px-5 py-3 ${tone.border} ${tone.head}`}>
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${tone.dot}`} aria-hidden />
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
            {lines.length}
          </span>
        </div>
        <p className="text-xs text-slate-500">{caption}</p>
      </div>

      {lines.length === 0 ? (
        <p className="px-5 py-6 text-center text-sm text-slate-400">
          No {title.toLowerCase()} on this invoice.
        </p>
      ) : (
        <table className="w-full">
          <tbody className="divide-y divide-slate-100">
            {lines.map((line) => (
              <tr key={line.id}>
                <td className="px-5 py-3">
                  <p className="text-sm text-slate-900">{line.description}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {line.kind === 'recurring' ? (
                      <>
                        {line.plan_name} · {line.cycle}
                        {line.period_start && (
                          <>
                            {' · '}
                            {line.period_start} → {line.period_end}
                          </>
                        )}
                      </>
                    ) : (
                      line.product_name ?? 'product'
                    )}
                  </p>
                </td>
                <td className="whitespace-nowrap px-5 py-3 text-right text-xs text-slate-500">
                  {parseFloat(line.qty)} × {formatCurrency(line.unit_price)}
                </td>
                <td className="whitespace-nowrap px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(line.amount)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className={`border-t ${tone.border} ${tone.head}`}>
              <td className="px-5 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500" colSpan={2}>
                {title} subtotal
              </td>
              <td className={`px-5 py-2.5 text-right text-sm font-semibold ${tone.subtotal}`}>
                {formatCurrency(subtotal)}
              </td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  )
}

function TotalsCard({ invoice }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Totals</h2>
      <div className="mt-2 divide-y divide-slate-100">
        <TotalRow label="One-time subtotal" value={invoice.one_time_subtotal} />
        <TotalRow label="Recurring subtotal" value={invoice.recurring_subtotal} />
        <TotalRow label="Invoice total" value={invoice.total_amount} strong />
        <TotalRow label="Paid" value={invoice.amount_paid} />
        {Number(invoice.amount_credited) > 0 && (
          <TotalRow label="Credited" value={invoice.amount_credited} />
        )}
        <TotalRow label="Balance due" value={invoice.balance_due} strong />
      </div>
    </div>
  )
}

function TotalRow({ label, value, strong }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <span className={`text-xs ${strong ? 'font-medium text-slate-700' : 'text-slate-500'}`}>
        {label}
      </span>
      <span className={`text-sm ${strong ? 'font-semibold text-slate-900' : 'text-slate-700'}`}>
        {formatCurrency(value)}
      </span>
    </div>
  )
}

function PaymentsCard({ invoice }) {
  const hasActivity = invoice.payments.length > 0 || invoice.credit_notes.length > 0

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Payments &amp; credits</h2>
      {!hasActivity ? (
        <p className="mt-3 text-sm text-slate-500">Nothing recorded yet.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {invoice.payments.map((payment) => (
            <div
              key={payment.id}
              className="flex items-baseline justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2"
            >
              <div>
                <p className="text-sm text-slate-900">{payment.method_label}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {new Date(payment.paid_at).toLocaleDateString()}
                  {payment.reference && ` · ${payment.reference}`}
                  {payment.recorded_by_name && ` · ${payment.recorded_by_name}`}
                </p>
              </div>
              <span className="whitespace-nowrap text-sm font-medium text-slate-900">
                {formatCurrency(payment.amount)}
              </span>
            </div>
          ))}
          {invoice.credit_notes.map((note) => (
            <div
              key={note.id}
              className="flex items-baseline justify-between gap-3 rounded-lg bg-emerald-50 px-3 py-2"
            >
              <div>
                <p className="text-sm text-emerald-900">Credit note</p>
                <p className="mt-0.5 text-xs text-emerald-700">{note.reason}</p>
              </div>
              <span className="whitespace-nowrap text-sm font-medium text-emerald-900">
                −{formatCurrency(note.amount)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PaymentDialog({ invoice, onClose }) {
  const [amount, setAmount] = useState(String(invoice.balance_due))
  const [method, setMethod] = useState('bank_transfer')
  const [reference, setReference] = useState('')
  const [pay, state] = useRecordPaymentMutation()
  const { formError, fieldErrors } = parseApiError(state.error)

  async function submit(event) {
    event.preventDefault()
    try {
      await pay({ id: invoice.id, amount, method, reference }).unwrap()
      onClose()
    } catch {
      /* surfaced below */
    }
  }

  return (
    <Modal
      title="Record payment"
      subtitle={`${invoice.invoice_number} — ${formatCurrency(invoice.balance_due)} outstanding`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Amount</span>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
          {fieldErrors.amount && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.amount}</span>
          )}
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Method</span>
          <select
            value={method}
            onChange={(event) => setMethod(event.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          >
            <option value="bank_transfer">Bank Transfer</option>
            <option value="card">Card</option>
            <option value="upi">UPI</option>
            <option value="cheque">Cheque</option>
          </select>
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Reference</span>
          <input
            value={reference}
            onChange={(event) => setReference(event.target.value)}
            placeholder="UTR / cheque no. / transaction id"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
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
            Cancel
          </button>
          <button
            type="submit"
            disabled={state.isLoading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {state.isLoading ? 'Recording…' : 'Record payment'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function CreditNoteDialog({ invoice, onClose }) {
  const [amount, setAmount] = useState(String(invoice.balance_due))
  const [reason, setReason] = useState('')
  const [issue, state] = useIssueCreditNoteMutation()
  const { formError, fieldErrors } = parseApiError(state.error)

  async function submit(event) {
    event.preventDefault()
    try {
      await issue({ id: invoice.id, amount, reason }).unwrap()
      onClose()
    } catch {
      /* surfaced below */
    }
  }

  return (
    <Modal
      title="Issue credit note"
      subtitle={`${invoice.invoice_number} — ${formatCurrency(invoice.balance_due)} outstanding`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Amount</span>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
          {fieldErrors.amount && (
            <span className="mt-1.5 block text-xs text-red-600">{fieldErrors.amount}</span>
          )}
        </label>

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Reason</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
            placeholder="Billing correction, dispute, goodwill adjustment…"
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
            Cancel
          </button>
          <button
            type="submit"
            disabled={state.isLoading}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
          >
            {state.isLoading ? 'Issuing…' : 'Issue credit note'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
