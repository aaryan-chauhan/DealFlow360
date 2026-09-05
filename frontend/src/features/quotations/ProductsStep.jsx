import { useState } from 'react'

import { useGetProductsQuery } from '../admin/catalogApi'
import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import { useAddLineMutation } from './quotationsApi'

const CATEGORIES = ['All Products', 'Hardware', 'Software', 'Services', 'Subscription']

function QtyStepper({ value, onChange }) {
  return (
    <div className="inline-flex items-center rounded-lg border border-slate-300">
      <button
        type="button"
        onClick={() => onChange(Math.max(1, value - 1))}
        className="px-2.5 py-1 text-slate-500 hover:text-slate-800"
        aria-label="Decrease quantity"
      >
        −
      </button>
      <input
        value={value}
        onChange={(e) => onChange(Math.max(1, Number(e.target.value) || 1))}
        className="w-12 border-x border-slate-300 py-1 text-center text-sm outline-none"
      />
      <button
        type="button"
        onClick={() => onChange(value + 1)}
        className="px-2.5 py-1 text-slate-500 hover:text-slate-800"
        aria-label="Increase quantity"
      >
        +
      </button>
    </div>
  )
}

export default function ProductsStep({ quotationId, lines }) {
  const [category, setCategory] = useState(CATEGORIES[0])
  const [search, setSearch] = useState('')
  const [quantities, setQuantities] = useState({})
  const { data: products = [], isLoading } = useGetProductsQuery(search || undefined)
  const [addLine, { isLoading: isAdding, error }] = useAddLineMutation()
  const { formError } = parseApiError(error)

  const visible =
    category === 'All Products' ? products : products.filter((p) => p.category === category)
  const inCart = new Set(lines.map((line) => line.product))

  async function handleAdd(product) {
    const qty = quantities[product.id] ?? 1
    try {
      await addLine({ quotationId, product: product.id, qty, discount_pct: 0 }).unwrap()
      setQuantities((q) => ({ ...q, [product.id]: 1 }))
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <div className="space-y-4">
      {formError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {formError}
        </div>
      )}

      <div className="flex gap-5">
        <aside className="w-44 shrink-0">
          <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Categories
          </p>
          <ul className="space-y-0.5">
            {CATEGORIES.map((item) => (
              <li key={item}>
                <button
                  onClick={() => setCategory(item)}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                    category === item
                      ? 'bg-brand-50 font-medium text-brand-700'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {item}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="flex-1 space-y-3">
          <div className="relative">
            <svg viewBox="0 0 24 24" className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search products..."
              className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Product</th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Unit Price</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Category</th>
                  <th className="px-5 py-3 text-center text-xs font-medium uppercase tracking-wide text-slate-500">Qty</th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-500">
                      Loading catalog…
                    </td>
                  </tr>
                )}
                {!isLoading && visible.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-500">
                      No products in this category.
                    </td>
                  </tr>
                )}
                {visible.map((product) => (
                  <tr key={product.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600">
                          {product.name.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{product.name}</p>
                          {inCart.has(product.id) && (
                            <p className="text-xs text-emerald-600">Already in this quote</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                      {formatCurrency(product.base_price)}
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{product.category}</td>
                    <td className="px-5 py-3 text-center">
                      <QtyStepper
                        value={quantities[product.id] ?? 1}
                        onChange={(qty) => setQuantities((q) => ({ ...q, [product.id]: qty }))}
                      />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => handleAdd(product)}
                        disabled={isAdding}
                        className="rounded-md bg-brand-600 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                      >
                        Add
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-slate-500">
            {lines.length} line{lines.length === 1 ? '' : 's'} on this quotation. Discounts are set
            on the next step.
          </p>
        </div>
      </div>
    </div>
  )
}
