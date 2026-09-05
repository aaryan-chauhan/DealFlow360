import { useState } from 'react'

import { parseApiError } from '../../shared/api/errors'
import { useGeneratePortalLinkMutation, useReplyToNegotiationMutation } from './quotationsApi'

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** The rep's view of the customer link.
 *
 *  The token is shown once and never again — the API keeps only a hash — so this panel
 *  holds the generated URL in component state and says plainly that re-generating
 *  invalidates the previous link. A rep who does not know that would otherwise "re-send"
 *  and silently break the link the customer already has open.
 */
function PortalLinkBox({ quotation }) {
  const [generate, { isLoading, error }] = useGeneratePortalLinkMutation()
  const [link, setLink] = useState(null)
  const [copied, setCopied] = useState(false)
  const { formError } = parseApiError(error)

  const existing = quotation.portal_link
  const shareable = ['pending_approval', 'approved', 'negotiation', 'confirmed'].includes(
    quotation.status,
  )

  async function handleGenerate() {
    try {
      const result = await generate(quotation.id).unwrap()
      setLink(result.portal_url)
      setCopied(false)
    } catch {
      /* surfaced through `formError` */
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
    } catch {
      // Clipboard access needs a secure context; over plain http on a LAN IP it is
      // blocked. The input below is selectable, so the rep can still copy by hand.
      setCopied(false)
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Customer portal</h2>
          <p className="mt-1 text-sm text-slate-500">
            {existing
              ? `A link is live until ${formatDate(existing.expires_at)}.`
              : 'No link has been sent to this customer yet.'}
            {existing?.last_used_at
              ? ` Last opened ${formatDate(existing.last_used_at)}.`
              : existing
                ? ' Not opened yet.'
                : ''}
          </p>
        </div>
        {shareable && (
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="whitespace-nowrap rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {isLoading ? 'Generating…' : existing ? 'Re-send link' : 'Send to Customer'}
          </button>
        )}
      </div>

      {!shareable && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3.5 py-2.5 text-sm text-slate-500">
          Submit this quotation for approval before sending it to the customer — a draft has
          not been through governance yet.
        </p>
      )}

      {formError && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {formError}
        </p>
      )}

      {link && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-900">
            Link ready — send this to {quotation.customer_name}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              readOnly
              value={link}
              onFocus={(event) => event.target.select()}
              className="min-w-[240px] flex-1 rounded-md border border-emerald-300 bg-white px-3 py-1.5 font-mono text-xs text-slate-700 outline-none"
            />
            <button
              onClick={copy}
              className="rounded-md bg-emerald-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <p className="mt-2 text-xs text-emerald-800">
            Shown once only — the server keeps just a hash of it. Generating another link
            immediately invalidates this one.
          </p>
        </div>
      )}
    </section>
  )
}

function Bubble({ message }) {
  const side = message.author_side

  if (side === 'system') {
    return (
      <li className="flex justify-center">
        <p className="max-w-lg rounded-lg bg-slate-100 px-3.5 py-2 text-center text-xs text-slate-600">
          {message.body}
        </p>
      </li>
    )
  }

  // Mirrored against the portal: the rep's own messages sit on the right there, so here
  // the *customer's* do — each side sees their own words on their own side.
  const mine = side === 'internal'
  return (
    <li className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex max-w-[80%] flex-col ${mine ? 'items-end' : 'items-start'}`}>
        <div className="mb-1 flex items-center gap-2 px-1">
          <span className="text-xs font-medium text-slate-700">{message.author_name}</span>
          {!mine && (
            <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-violet-700">
              Customer
            </span>
          )}
          <span className="text-[11px] text-slate-400">{formatTime(message.created_at)}</span>
        </div>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm ${
            mine
              ? 'rounded-br-sm bg-brand-600 text-white'
              : 'rounded-bl-sm border border-violet-200 bg-violet-50 text-slate-800'
          }`}
        >
          {message.message_type === 'counter_offer' && (
            <p className="mb-1 text-xs font-semibold text-violet-700">
              Counter-offer: {parseFloat(message.counter_discount_pct)}%
              {message.line_label ? ` on ${message.line_label}` : ' on the whole quote'}
            </p>
          )}
          {message.message_type === 'confirmation' && (
            <p className="mb-1 text-xs font-semibold text-emerald-700">Quote accepted</p>
          )}
          {message.body && <p className="whitespace-pre-wrap">{message.body}</p>}
        </div>
      </div>
    </li>
  )
}

/** The customer thread, on the internal quotation screen (§5.9).
 *
 *  Same rows the portal renders, reached through the workspace's own auth. Without this
 *  the rep negotiates blind — the customer types into a portal nobody internal can see.
 */
export default function NegotiationPanel({ quotation }) {
  const messages = quotation.negotiation ?? []
  const [body, setBody] = useState('')
  const [reply, { isLoading, error }] = useReplyToNegotiationMutation()
  const { formError } = parseApiError(error)

  async function send() {
    if (!body.trim()) return
    try {
      await reply({ quotationId: quotation.id, body: body.trim() }).unwrap()
      setBody('')
    } catch {
      /* surfaced through `formError` */
    }
  }

  return (
    <div className="space-y-5">
      <PortalLinkBox quotation={quotation} />

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-slate-900">Customer negotiation</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            One thread, shared with {quotation.customer_name}&apos;s portal. Counter-offers
            posted here re-score the quotation automatically.
          </p>
        </div>

        <div className="max-h-[360px] overflow-y-auto px-5 py-4">
          {messages.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">
              No messages yet. Send the portal link above to start the conversation.
            </p>
          ) : (
            <ul className="space-y-4">
              {messages.map((message) => (
                <Bubble key={message.id} message={message} />
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-2 border-t border-slate-200 bg-slate-50 px-5 py-4">
          {formError && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
              {formError}
            </p>
          )}
          <div className="flex gap-2">
            <input
              value={body}
              onChange={(event) => setBody(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && send()}
              placeholder={`Reply to ${quotation.customer_name}…`}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
            />
            <button
              onClick={send}
              disabled={isLoading || !body.trim()}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {isLoading ? 'Sending…' : 'Reply'}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
