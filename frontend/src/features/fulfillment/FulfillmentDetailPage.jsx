import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import {
  useAcceptSplitMutation,
  useConsolidateBackorderMutation,
  useGetFulfillmentOrderQuery,
  useNotifyBackorderCustomerMutation,
  useOverrideSplitMutation,
  useScanReplenishmentMutation,
} from './fulfillmentApi'

const num = (value) => parseFloat(value ?? 0)
const key = (productId, warehouseId) => `${productId}:${warehouseId}`

function RowStatus({ row }) {
  if (row.is_backorder) {
    return (
      <span className="inline-flex whitespace-nowrap rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
        Backorder – {num(row.qty_backordered)} short
      </span>
    )
  }
  const used = row.allocations.filter((allocation) => num(allocation.qty) > 0).length
  if (used > 1) {
    return (
      <span className="inline-flex whitespace-nowrap rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
        Split across {used}
      </span>
    )
  }
  return (
    <span className="inline-flex whitespace-nowrap rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
      In stock
    </span>
  )
}

/** The shortfall alert from the wireframe. It never resolves itself — a shortfall stays on
 *  screen until someone notifies the customer or consolidates replenished stock. */
function BackorderBanner({ order, canManage, onNotify, onConsolidate, notifyState, consolidateState }) {
  const shortRows = order.rows.filter((row) => row.is_backorder)
  if (shortRows.length === 0) return null

  const readyRows = shortRows.filter((row) => row.consolidation_available)
  const notifiedAt = order.open_backorder?.customer_notified_at

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex gap-3">
          <svg viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 text-red-600" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <h2 className="text-sm font-semibold text-red-900">Backorder Alert</h2>
            <ul className="mt-1 space-y-0.5 text-sm text-red-800">
              {shortRows.map((row) => (
                <li key={row.product}>
                  <strong>{row.product_name}</strong> — {num(row.qty_backordered)} {row.unit}
                  {num(row.qty_backordered) === 1 ? '' : 's'} short of the {num(row.qty_needed)}{' '}
                  ordered. Available stock covers {num(row.qty_allocated)}.
                </li>
              ))}
            </ul>
            {notifiedAt && (
              <p className="mt-1.5 text-xs text-red-700">
                Customer notified on {new Date(notifiedAt).toLocaleString('en-IN')}.
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={onNotify}
            disabled={!canManage || notifyState.isLoading}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {notifyState.isLoading ? 'Notifying…' : 'Notify Customer'}
          </button>
          {readyRows.length > 0 && (
            <button
              onClick={onConsolidate}
              disabled={!canManage || consolidateState.isLoading}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {consolidateState.isLoading ? 'Consolidating…' : 'Consolidate Remaining Backorder'}
            </button>
          )}
        </div>
      </div>

      {readyRows.length > 0 && (
        <p className="mt-3 border-t border-red-200 pt-2.5 text-xs text-red-800">
          Stock has been replenished for {readyRows.map((row) => row.product_name).join(', ')}. The
          watcher only flags this — nothing ships until you consolidate.
        </p>
      )}

      {readyRows.length === 0 && order.status === 'suggested' && (
        <p className="mt-3 border-t border-red-200 pt-2.5 text-xs text-red-800">
          This split is still only a suggestion, so no stock is held against it yet. Accept it
          below to reserve the available units — the replenishment watcher then tracks the
          shortfall and lights up <strong>Consolidate Remaining Backorder</strong> here as soon as
          stock catches up.
        </p>
      )}
    </div>
  )
}

export default function FulfillmentDetailPage() {
  const { id } = useParams()
  const { data: order, isLoading } = useGetFulfillmentOrderQuery(id)
  const [accept, acceptState] = useAcceptSplitMutation()
  const [override, overrideState] = useOverrideSplitMutation()
  const [consolidate, consolidateState] = useConsolidateBackorderMutation()
  const [notify, notifyState] = useNotifyBackorderCustomerMutation()
  const [scan, scanState] = useScanReplenishmentMutation()

  // product id currently being hand-edited, plus the working quantities for the whole
  // table — an override replaces every line, so the untouched rows travel with it.
  const [editing, setEditing] = useState(null)
  const [draft, setDraft] = useState({})

  const suggested = useMemo(() => {
    const values = {}
    for (const row of order?.rows ?? []) {
      for (const allocation of row.allocations) {
        values[key(row.product, allocation.warehouse)] = String(num(allocation.qty))
      }
    }
    return values
  }, [order])

  if (isLoading) return <p className="text-sm text-slate-500">Loading fulfillment order…</p>
  if (!order) return <p className="text-sm text-slate-500">Fulfillment order not found.</p>

  const canManage = order.can_manage
  const isClosed = order.status === 'fulfilled' || order.status === 'cancelled'
  const { formError } = parseApiError(
    acceptState.error ?? overrideState.error ?? consolidateState.error ?? notifyState.error,
  )
  const overrideErrors = overrideState.error?.data?.lines ?? []

  const value = (productId, warehouseId) =>
    draft[key(productId, warehouseId)] ?? suggested[key(productId, warehouseId)] ?? '0'

  function startOverride(productId) {
    setDraft({ ...suggested, ...draft })
    setEditing(productId)
  }

  function cancelOverride() {
    setEditing(null)
    setDraft({})
  }

  async function saveOverride() {
    const lines = []
    for (const row of order.rows) {
      for (const allocation of row.allocations) {
        lines.push({
          product: row.product,
          warehouse: allocation.warehouse,
          qty: value(row.product, allocation.warehouse) || '0',
        })
      }
    }
    try {
      await override({ id, lines, reason: 'Manual warehouse split override.' }).unwrap()
      cancelOverride()
    } catch {
      /* surfaced in the banner above the table */
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            Fulfillment &amp; Stock Allocation – {order.quotation_number}
          </h1>
          <StatusPill value={order.status} label={order.status_label} />
        </div>
        <Link to="/fulfillment" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          All fulfillment orders
        </Link>
      </div>

      {formError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          <p>{formError}</p>
          {overrideErrors.length > 0 && (
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
              {overrideErrors.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <BackorderBanner
        order={order}
        canManage={canManage}
        notifyState={notifyState}
        consolidateState={consolidateState}
        onNotify={() => notify({ id })}
        onConsolidate={() => consolidate({ id })}
      />

      <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-5 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Warehouse Split</h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Cheapest warehouse first, one shipment where possible — {order.shipment_count}{' '}
                shipment{order.shipment_count === 1 ? '' : 's'} planned.
              </p>
            </div>
            {editing && (
              <div className="flex gap-2">
                <button
                  onClick={cancelOverride}
                  className="rounded-lg border border-slate-300 px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={saveOverride}
                  disabled={overrideState.isLoading}
                  className="rounded-lg bg-brand-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  {overrideState.isLoading ? 'Saving…' : 'Save override'}
                </button>
              </div>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    Product
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">
                    Total Qty
                  </th>
                  {order.warehouses.map((warehouse) => (
                    <th
                      key={warehouse.id}
                      className="px-3 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500"
                    >
                      {warehouse.name}
                      <span className="block font-normal normal-case text-slate-400">
                        cost weight {num(warehouse.shipping_cost_weight)}
                      </span>
                    </th>
                  ))}
                  <th className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    Status
                  </th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {order.rows.map((row) => {
                  const isEditing = editing === row.product
                  return (
                    <tr key={row.product} className={isEditing ? 'bg-brand-50/40' : ''}>
                      <td className="px-5 py-3">
                        <p className="text-sm font-medium text-slate-900">{row.product_name}</p>
                        <p className="text-xs text-slate-500">
                          {row.category}
                          {row.is_override && ' · manually overridden'}
                        </p>
                      </td>
                      <td className="px-3 py-3 text-right text-sm font-medium text-slate-900">
                        {num(row.qty_needed)}
                      </td>
                      {row.allocations.map((allocation) => (
                        <td key={allocation.warehouse} className="px-3 py-3 text-right">
                          {isEditing ? (
                            <>
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={value(row.product, allocation.warehouse)}
                                onChange={(e) =>
                                  setDraft({
                                    ...draft,
                                    [key(row.product, allocation.warehouse)]: e.target.value,
                                  })
                                }
                                className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
                              />
                              <span className="mt-1 block text-xs text-slate-400">
                                max {num(allocation.qty_available)}
                              </span>
                            </>
                          ) : (
                            <>
                              <span
                                className={`text-sm ${
                                  num(allocation.qty) > 0
                                    ? 'font-medium text-slate-900'
                                    : 'text-slate-300'
                                }`}
                              >
                                {num(allocation.qty)}
                              </span>
                              <span className="mt-0.5 block text-xs text-slate-400">
                                {num(allocation.qty_available)} avail.
                              </span>
                            </>
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-3">
                        <RowStatus row={row} />
                      </td>
                      <td className="px-5 py-3 text-right">
                        {!isEditing && (
                          <button
                            onClick={() => startOverride(row.product)}
                            disabled={!canManage || isClosed || Boolean(editing)}
                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Override
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 px-5 py-4">
            <button
              onClick={() => accept(id)}
              disabled={!canManage || isClosed || acceptState.isLoading || Boolean(editing)}
              className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {acceptState.isLoading ? 'Reserving stock…' : 'Accept Suggested Split'}
            </button>
            <button
              onClick={() => scan()}
              disabled={scanState.isLoading}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {scanState.isLoading ? 'Scanning…' : 'Check stock replenishment'}
            </button>
            {scanState.data && (
              <p className="text-xs text-slate-600">
                {scanState.data.flagged.length > 0
                  ? `Stock caught up on ${scanState.data.flagged.length} backorder line(s) — see the alert above.`
                  : 'Scan complete: no backorder line has enough stock to consolidate yet.'}
              </p>
            )}
            {!canManage && (
              <p className="text-xs text-slate-500">
                Only Finance / Ops or an Admin can accept or override a split — the API enforces
                this independently.
              </p>
            )}
          </div>
        </section>

        <aside className="space-y-5">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Order Summary</h2>
            <dl className="mt-4 space-y-2 text-sm">
              {[
                ['Customer', order.customer_name],
                ['Owner', order.owner_name],
                ['Quote value', formatCurrency(order.total_value)],
                ['Quote status', order.quotation_status],
                ['Shipments', order.shipment_count],
                ['Promised date', order.promised_date ?? '—'],
              ].map(([label, content]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="text-right font-medium text-slate-900">{content}</dd>
                </div>
              ))}
            </dl>
            <Link
              to={`/quotations/${order.quotation}`}
              className="mt-4 block rounded-lg border border-slate-300 py-2 text-center text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              View full quotation
            </Link>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Backorder History</h2>
            <ul className="mt-3 divide-y divide-slate-100">
              {order.backorder_events.length === 0 && (
                <li className="py-2.5 text-sm text-slate-500">
                  No backorder has been raised on this order.
                </li>
              )}
              {order.backorder_events.map((event) => (
                <li key={event.id} className="py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-slate-900">
                      {new Date(event.triggered_at).toLocaleDateString('en-IN')}
                    </span>
                    <StatusPill
                      value={event.resolved ? 'approved' : 'pending'}
                      label={event.resolved ? 'Resolved' : 'Open'}
                    />
                  </div>
                  {event.resolution_note && (
                    <p className="mt-0.5 text-xs text-slate-500">{event.resolution_note}</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}
