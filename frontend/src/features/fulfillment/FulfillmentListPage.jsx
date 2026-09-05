import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatCurrency } from '../../shared/format'
import StatusPill from '../../shared/ui/StatusPill'
import { useGetFulfillmentOrdersQuery, useScanReplenishmentMutation } from './fulfillmentApi'

const TABS = [
  { label: 'All', value: '' },
  { label: 'Needs Action', value: 'suggested' },
  { label: 'Backordered', value: 'backordered' },
  { label: 'Accepted', value: 'accepted' },
]

export default function FulfillmentListPage() {
  const [tab, setTab] = useState('')
  const { data: orders = [], isLoading } = useGetFulfillmentOrdersQuery(
    tab ? { status: tab } : undefined,
  )
  const [scan, scanState] = useScanReplenishmentMutation()

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            Fulfillment &amp; Stock Allocation
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Every approved quotation gets a suggested warehouse split automatically. Accept it or
            override the quantities per warehouse.
          </p>
        </div>
        <div className="text-right">
          <button
            onClick={() => scan()}
            disabled={scanState.isLoading}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {scanState.isLoading ? 'Scanning…' : 'Check stock replenishment'}
          </button>
          {scanState.data && (
            <p className="mt-1.5 text-xs text-slate-500">
              {scanState.data.flagged.length > 0
                ? `${scanState.data.flagged.length} backorder line(s) can now be consolidated.`
                : 'No backorder line has enough stock yet.'}
            </p>
          )}
        </div>
      </div>

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
              {['Order', 'Customer', 'Owner', 'Value', 'Warehouse(s)', 'Promised', 'Status'].map(
                (heading, index) => (
                  <th
                    key={heading}
                    className={`px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 ${
                      index === 3 ? 'text-right' : 'text-left'
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
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading fulfillment orders…
                </td>
              </tr>
            )}
            {!isLoading && orders.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-sm text-slate-500">
                  Nothing here. A fulfillment order appears as soon as a quotation is approved.
                </td>
              </tr>
            )}
            {orders.map((order) => (
              <tr key={order.id} className="hover:bg-slate-50">
                <td className="px-5 py-3">
                  <Link
                    to={`/fulfillment/${order.id}`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    {order.quotation_number}
                  </Link>
                </td>
                <td className="px-5 py-3 text-sm text-slate-900">{order.customer_name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{order.owner_name}</td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatCurrency(order.total_value)}
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {order.warehouse_names.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {order.warehouse_names.map((name) => (
                        <span
                          key={name}
                          className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                        >
                          {name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">nothing allocated</span>
                  )}
                  <span className="mt-0.5 block text-xs text-slate-400">
                    {order.shipment_count} shipment{order.shipment_count === 1 ? '' : 's'}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">{order.promised_date ?? '—'}</td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusPill value={order.status} label={order.status_label} />
                    {order.has_backorder && (
                      <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                        Backorder
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
