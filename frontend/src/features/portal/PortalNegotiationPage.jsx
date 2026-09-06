import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import {
  useConfirmQuotationMutation,
  useGetPortalQuotationQuery,
  usePostCommentMutation,
  usePostCounterOfferMutation,
  usePostDeliveryDateRequestMutation,
} from './portalApi'

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})
const money = (value) => currency.format(Number(value ?? 0))
const pct = (value) => `${parseFloat(value ?? 0)}%`

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** The customer's own vocabulary, not the internal status machine's. "Pending approval"
 *  would invite the question "approval by whom?" — which is not the customer's business. */
const BANNERS = {
  approved: {
    label: 'Sent — awaiting your response',
    tone: 'border-blue-200 bg-blue-50 text-blue-900',
    dot: 'bg-blue-500',
    note: 'This quotation is ready for you. Accept it, or send a counter-offer below.',
  },
  negotiation: {
    label: 'Under negotiation',
    tone: 'border-violet-200 bg-violet-50 text-violet-900',
    dot: 'bg-violet-500',
    note: 'Your counter-offer has been applied to the quotation below. Accept it when you are happy with the terms.',
  },
  pending_approval: {
    label: 'With our team for review',
    tone: 'border-amber-200 bg-amber-50 text-amber-900',
    dot: 'bg-amber-500',
    note: 'The terms you asked for need an internal sign-off. Nothing further is needed from you — we will be in touch shortly.',
  },
  confirmed: {
    label: 'Confirmed',
    tone: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    dot: 'bg-emerald-500',
    note: 'Thank you — this quotation is accepted and has moved into fulfillment.',
  },
  rejected: {
    label: 'Withdrawn',
    tone: 'border-slate-200 bg-slate-50 text-slate-700',
    dot: 'bg-slate-400',
    note: 'This quotation is no longer active. Please contact your account manager.',
  },
}

function StatusBanner({ quotation }) {
  const banner = BANNERS[quotation.status] ?? BANNERS.approved
  return (
    <div className={`rounded-xl border px-5 py-4 ${banner.tone}`}>
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${banner.dot}`} />
        <h2 className="text-sm font-semibold">{banner.label}</h2>
      </div>
      <p className="mt-1.5 text-sm opacity-90">{banner.note}</p>
    </div>
  )
}

function Bubble({ message }) {
  const side = message.author_side
  const mine = side === 'customer'

  if (side === 'system') {
    return (
      <li className="flex justify-center">
        <p className="max-w-lg rounded-lg bg-slate-100 px-3.5 py-2 text-center text-xs text-slate-600">
          {message.body}
        </p>
      </li>
    )
  }

  return (
    <li className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] ${mine ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className="mb-1 flex items-center gap-2 px-1">
          <span className="text-xs font-medium text-slate-700">{message.author_name}</span>
          <span className="text-[11px] text-slate-400">{formatTime(message.created_at)}</span>
        </div>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm ${
            mine
              ? 'rounded-br-sm bg-brand-600 text-white'
              : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800'
          }`}
        >
          {message.message_type === 'counter_offer' && (
            <p
              className={`mb-1 text-xs font-semibold ${mine ? 'text-blue-100' : 'text-brand-700'}`}
            >
              Counter-offer: {pct(message.counter_discount_pct)}
              {message.line_label ? ` on ${message.line_label}` : ' on the whole quote'}
            </p>
          )}
          {message.message_type === 'delivery_date_request' && (
            <p
              className={`mb-1 text-xs font-semibold ${mine ? 'text-blue-100' : 'text-brand-700'}`}
            >
              Requested delivery: {formatDate(message.requested_delivery_date)}
              {message.line_label ? ` for ${message.line_label}` : ''}
            </p>
          )}
          {message.message_type === 'confirmation' && (
            <p
              className={`mb-1 text-xs font-semibold ${mine ? 'text-blue-100' : 'text-emerald-700'}`}
            >
              Quote accepted
            </p>
          )}
          {message.body && <p className="whitespace-pre-wrap">{message.body}</p>}
        </div>
      </div>
    </li>
  )
}

function MessageThread({ messages }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [messages.length])

  return (
    <div className="max-h-[420px] overflow-y-auto px-5 py-4">
      {messages.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">
          No messages yet — start the conversation below.
        </p>
      ) : (
        <ul className="space-y-4">
          {messages.map((message) => (
            <Bubble key={message.id} message={message} />
          ))}
          <li ref={endRef} />
        </ul>
      )}
    </div>
  )
}

/** Errors from the portal API. Kept separate from the workspace's `parseApiError` so the
 *  two surfaces cannot drift into sharing modules — and so the portal never renders a
 *  DRF field error that was written for an internal audience. */
function portalError(error) {
  if (!error) return null
  if (error.status === 'FETCH_ERROR') return 'Cannot reach the server. Please try again.'
  const data = error.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  const first = data && Object.values(data)[0]
  if (Array.isArray(first)) return first.join(' ')
  if (typeof first === 'string') return first
  return 'Something went wrong. Please try again.'
}

function QuoteTable({ quotation }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px]">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              Item
            </th>
            <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wide text-slate-500">
              Qty
            </th>
            <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">
              Unit Price
            </th>
            <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">
              Discount
            </th>
            <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">
              Total
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {quotation.lines.map((line) => (
            <tr key={line.id}>
              <td className="px-5 py-3">
                <p className="text-sm font-medium text-slate-900">{line.product_name}</p>
                <p className="text-xs text-slate-500">
                  {line.product_category}
                  {line.variant_label ? ` · ${line.variant_label}` : ''}
                  {line.line_type === 'recurring' ? ' · Recurring' : ''}
                </p>
              </td>
              <td className="px-5 py-3 text-center text-sm text-slate-700">
                {parseFloat(line.qty)}
              </td>
              <td className="px-5 py-3 text-right text-sm text-slate-700">
                {money(line.unit_price)}
              </td>
              <td className="px-5 py-3 text-right text-sm text-slate-700">
                {parseFloat(line.discount_pct) > 0 ? (
                  <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-emerald-700">
                    {pct(line.discount_pct)}
                  </span>
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
              <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                {money(line.line_total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ActionPanel({ token, quotation, onBusyChange }) {
  const [comment, setComment] = useState('')
  const [discount, setDiscount] = useState('')
  const [scope, setScope] = useState('')
  const [showCounter, setShowCounter] = useState(false)
  const [showDelivery, setShowDelivery] = useState(false)
  const [deliveryDate, setDeliveryDate] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [notice, setNotice] = useState(null)

  const [postComment, commentState] = usePostCommentMutation()
  const [postCounterOffer, counterState] = usePostCounterOfferMutation()
  const [postDeliveryDateRequest, deliveryState] = usePostDeliveryDateRequestMutation()
  const [confirmQuotation, confirmState] = useConfirmQuotationMutation()

  const busy =
    commentState.isLoading ||
    counterState.isLoading ||
    deliveryState.isLoading ||
    confirmState.isLoading
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])

  const error =
    portalError(commentState.error) ??
    portalError(counterState.error) ??
    portalError(deliveryState.error) ??
    portalError(confirmState.error)

  if (!quotation.can_act) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
        {quotation.status === 'confirmed'
          ? 'This quotation is confirmed. Your account manager will follow up with delivery details.'
          : 'This quotation is with our team right now, so it cannot be changed from here.'}
      </div>
    )
  }

  async function send() {
    if (!comment.trim()) return
    try {
      await postComment({ token, body: comment.trim() }).unwrap()
      setComment('')
      setNotice(null)
    } catch {
      /* surfaced through `error` */
    }
  }

  async function sendCounter() {
    const value = Number(discount)
    if (Number.isNaN(value) || value < 0 || value > 100) return
    try {
      const result = await postCounterOffer({
        token,
        counter_discount_pct: value,
        body: comment.trim(),
        // The token already fixes the quotation; sending the id lets the server reject a
        // mismatch loudly rather than acting on the wrong record.
        quotation: quotation.id,
        quotation_line: scope || null,
      }).unwrap()
      setComment('')
      setDiscount('')
      setShowCounter(false)
      setNotice(
        result.sent_for_approval
          ? 'Your counter-offer has been sent to our team for approval.'
          : 'Your counter-offer has been applied to the quotation.',
      )
    } catch {
      /* surfaced through `error` */
    }
  }

  async function sendDeliveryDate() {
    if (!deliveryDate) return
    try {
      await postDeliveryDateRequest({
        token,
        requested_delivery_date: deliveryDate,
        body: comment.trim(),
        quotation: quotation.id,
        quotation_line: scope || null,
      }).unwrap()
      setComment('')
      setDeliveryDate('')
      setShowDelivery(false)
      setNotice('Your preferred delivery date has been shared with your account manager.')
    } catch {
      /* surfaced through `error` */
    }
  }

  async function accept() {
    try {
      const result = await confirmQuotation({
        token,
        body: comment.trim(),
        quotation: quotation.id,
      }).unwrap()
      setComment('')
      setConfirming(false)
      setNotice(
        result.confirmed
          ? 'Thank you — your quotation is confirmed.'
          : 'These terms need an internal sign-off first. We will be in touch shortly.',
      )
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && !error && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      <div>
        <label htmlFor="portal-message" className="text-sm font-medium text-slate-900">
          Message
        </label>
        <textarea
          id="portal-message"
          rows={3}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Ask a question, or add a note to your counter-offer…"
          className="mt-1.5 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
        />
      </div>

      {showCounter && (
        <div className="space-y-3 rounded-lg border border-violet-200 bg-violet-50 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor="portal-discount" className="text-xs font-medium text-violet-900">
                Discount you are asking for
              </label>
              <div className="mt-1 flex items-center gap-1">
                <input
                  id="portal-discount"
                  value={discount}
                  onChange={(event) => setDiscount(event.target.value)}
                  inputMode="decimal"
                  placeholder="15"
                  className="w-24 rounded-md border border-violet-300 px-2.5 py-1.5 text-right text-sm outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                />
                <span className="text-sm text-violet-800">%</span>
              </div>
            </div>
            <div className="min-w-[200px] flex-1">
              <label htmlFor="portal-scope" className="text-xs font-medium text-violet-900">
                Applies to
              </label>
              <select
                id="portal-scope"
                value={scope}
                onChange={(event) => setScope(event.target.value)}
                className="mt-1 w-full rounded-md border border-violet-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-violet-500"
              >
                <option value="">Every item on this quote</option>
                {quotation.lines.map((line) => (
                  <option key={line.id} value={line.id}>
                    {line.product_name} only
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-violet-800">
            This replaces the discount currently shown on{' '}
            {scope
              ? quotation.lines.find((line) => line.id === scope)?.product_name
              : 'every line'}
            . We will confirm straight away whether we can hold it.
          </p>
          <div className="flex gap-2">
            <button
              onClick={sendCounter}
              disabled={busy || discount === ''}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-60"
            >
              {counterState.isLoading ? 'Sending…' : 'Send counter-offer'}
            </button>
            <button
              onClick={() => setShowCounter(false)}
              className="rounded-lg border border-violet-300 px-4 py-2 text-sm font-medium text-violet-800 hover:bg-violet-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {showDelivery && (
        <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor="portal-delivery-date" className="text-xs font-medium text-blue-900">
                Preferred delivery date
              </label>
              <input
                id="portal-delivery-date"
                type="date"
                value={deliveryDate}
                onChange={(event) => setDeliveryDate(event.target.value)}
                className="mt-1 rounded-md border border-blue-300 px-2.5 py-1.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <div className="min-w-[200px] flex-1">
              <label htmlFor="portal-delivery-scope" className="text-xs font-medium text-blue-900">
                Applies to
              </label>
              <select
                id="portal-delivery-scope"
                value={scope}
                onChange={(event) => setScope(event.target.value)}
                className="mt-1 w-full rounded-md border border-blue-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-500"
              >
                <option value="">The whole order</option>
                {quotation.lines.map((line) => (
                  <option key={line.id} value={line.id}>
                    {line.product_name} only
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-blue-800">
            This is a request — your account manager will confirm whether it can be promised.
          </p>
          <div className="flex gap-2">
            <button
              onClick={sendDeliveryDate}
              disabled={busy || !deliveryDate}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {deliveryState.isLoading ? 'Sending…' : 'Send request'}
            </button>
            <button
              onClick={() => setShowDelivery(false)}
              className="rounded-lg border border-blue-300 px-4 py-2 text-sm font-medium text-blue-800 hover:bg-blue-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {confirming && (
        <div className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm text-emerald-900">
            Accept this quotation at <strong>{money(quotation.totals.net)}</strong>? This
            confirms the order and starts fulfillment.
          </p>
          <div className="flex gap-2">
            <button
              onClick={accept}
              disabled={busy}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
            >
              {confirmState.isLoading ? 'Confirming…' : 'Yes, accept'}
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
        <button
          onClick={() => {
            setConfirming(true)
            setShowCounter(false)
            setShowDelivery(false)
          }}
          disabled={busy}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          Accept Quote
        </button>
        <button
          onClick={() => {
            setShowCounter(true)
            setShowDelivery(false)
            setConfirming(false)
          }}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          Request Changes
        </button>
        <button
          onClick={() => {
            setShowDelivery(true)
            setShowCounter(false)
            setConfirming(false)
          }}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          Request Delivery Date
        </button>
        <button
          onClick={send}
          disabled={busy || !comment.trim()}
          className="ml-auto rounded-lg border border-brand-600 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
        >
          {commentState.isLoading ? 'Sending…' : 'Send message'}
        </button>
      </div>
    </div>
  )
}

function ProfilePanel({ quotation }) {
  const rows = [
    ['Company', quotation.customer_name],
    ['Account tier', quotation.customer_tier],
    ['Email', quotation.customer_email],
    ['Location', quotation.customer_location || '—'],
    ['Your account manager', quotation.owner_name],
    ['Supplier', quotation.company_name],
  ]
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Your details</h2>
      <dl className="mt-4 space-y-2.5 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-right font-medium text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400">
        This link shows one quotation only and expires automatically. It is not a login —
        closing this tab ends the session.
      </p>
    </section>
  )
}

function InvalidLink({ message }) {
  return (
    <div className="mx-auto mt-24 max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
        <svg
          viewBox="0 0 24 24"
          className="h-6 w-6 text-amber-600"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        >
          <path d="M12 8v5M12 16.5h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        </svg>
      </div>
      <h1 className="mt-4 text-lg font-semibold text-slate-900">This link isn’t valid</h1>
      <p className="mt-2 text-sm text-slate-600">{message}</p>
      <p className="mt-4 text-xs text-slate-400">
        Portal links are issued for a single quotation and expire after a few days.
      </p>
    </div>
  )
}

const TABS = [
  ['quote', 'My Quotation'],
  ['messages', 'Messages'],
  ['profile', 'Profile'],
]

export default function PortalNegotiationPage() {
  const { token } = useParams()
  const [tab, setTab] = useState('quote')
  const { data, isLoading, error } = useGetPortalQuotationQuery(token)

  if (isLoading) {
    return <p className="mt-24 text-center text-sm text-slate-500">Loading your quotation…</p>
  }
  if (error) {
    return <InvalidLink message={portalError(error)} />
  }

  const quotation = data.quotation
  const totals = quotation.totals
  const messageCount = quotation.messages.filter((m) => m.author_side !== 'system').length

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-4 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              D
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-slate-900">DealFlow360</p>
              <p className="text-xs text-slate-500">Customer Portal</p>
            </div>
          </div>
          <nav className="flex gap-1">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`rounded-lg px-3 py-1.5 text-sm transition ${
                  tab === key
                    ? 'bg-slate-100 font-medium text-slate-900'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {label}
                {key === 'messages' && messageCount > 0 && (
                  <span className="ml-1.5 rounded-full bg-brand-600 px-1.5 py-0.5 text-[11px] font-medium text-white">
                    {messageCount}
                  </span>
                )}
              </button>
            ))}
          </nav>
          <p className="ml-auto text-sm text-slate-600">{quotation.customer_name}</p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-5 py-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              Quotation {quotation.number}
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              From {quotation.company_name} · valid till {formatDate(quotation.valid_till)}
            </p>
          </div>
          <p className="text-right">
            <span className="block text-xs uppercase tracking-wide text-slate-400">
              Quote total
            </span>
            <span className="text-2xl font-semibold text-slate-900">{money(totals.net)}</span>
          </p>
        </div>

        <StatusBanner quotation={quotation} />

        {tab === 'profile' && <ProfilePanel quotation={quotation} />}

        {tab !== 'profile' && (
          <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
            <div className="space-y-5">
              {tab === 'quote' && (
                <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <div className="border-b border-slate-200 px-5 py-3.5">
                    <h2 className="text-sm font-semibold text-slate-900">Quote summary</h2>
                  </div>
                  <QuoteTable quotation={quotation} />
                  <dl className="space-y-1.5 border-t border-slate-200 bg-slate-50 px-5 py-4 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Subtotal</dt>
                      <dd className="text-slate-700">{money(totals.gross)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">
                        Discount ({pct(totals.average_discount_pct)})
                      </dt>
                      <dd className="text-emerald-700">−{money(totals.discount)}</dd>
                    </div>
                    <div className="flex justify-between border-t border-slate-200 pt-1.5">
                      <dt className="font-semibold text-slate-900">Total</dt>
                      <dd className="text-base font-semibold text-slate-900">
                        {money(totals.net)}
                      </dd>
                    </div>
                  </dl>
                </section>
              )}

              <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-200 px-5 py-3.5">
                  <h2 className="text-sm font-semibold text-slate-900">Messages</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    You and {quotation.owner_name}
                  </p>
                </div>
                <MessageThread messages={quotation.messages} />
              </section>

              <ActionPanel token={token} quotation={quotation} />
            </div>

            <aside className="space-y-5">
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-slate-900">At a glance</h2>
                <dl className="mt-4 space-y-2.5 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Quote number</dt>
                    <dd className="font-medium text-slate-900">{quotation.number}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Issued</dt>
                    <dd className="text-slate-700">{formatDate(quotation.created_at)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Valid till</dt>
                    <dd className="text-slate-700">{formatDate(quotation.valid_till)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Items</dt>
                    <dd className="text-slate-700">{quotation.lines.length}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Account tier</dt>
                    <dd className="text-slate-700">{quotation.customer_tier}</dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-slate-900">Your contact</h2>
                <p className="mt-2 text-sm text-slate-700">{quotation.owner_name}</p>
                <p className="text-xs text-slate-500">{quotation.company_name}</p>
              </section>
            </aside>
          </div>
        )}

        <p className="pb-6 text-center text-xs text-slate-400">
          Secure single-quotation link · expires{' '}
          {formatDate(data.session.expires_at)}
        </p>
      </main>
    </div>
  )
}
