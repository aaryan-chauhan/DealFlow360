import { useMemo, useState } from 'react'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import SelectField from '../../shared/ui/SelectField'
import TextField from '../../shared/ui/TextField'
import {
  useCreatePriceListMutation,
  useCreateProductMutation,
  useCreateVariantMutation,
  useGetPriceListsQuery,
  useGetProductsQuery,
} from './catalogApi'

const TABS = ['All Products', 'Price Lists', 'Categories', 'Variants']
const CATEGORIES = ['Hardware', 'Software', 'Services', 'Subscription']
const CATEGORY_TINT = {
  Hardware: 'bg-blue-100 text-blue-700',
  Software: 'bg-violet-100 text-violet-700',
  Services: 'bg-emerald-100 text-emerald-700',
  Subscription: 'bg-amber-100 text-amber-700',
}

function StatusPill({ active }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
        active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
      }`}
    >
      {active ? 'Active' : 'Inactive'}
    </span>
  )
}

function Card({ children }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">{children}</div>
  )
}

function Th({ children, className = '' }) {
  return (
    <th className={`px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 ${className}`}>
      {children}
    </th>
  )
}

function EmptyRow({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-5 py-10 text-center text-sm text-slate-500">
        {children}
      </td>
    </tr>
  )
}

function AddProductModal({ onClose }) {
  const [form, setForm] = useState({
    name: '',
    category: 'Hardware',
    base_price: '',
    unit: 'unit',
    tax_pct: '18',
    description: '',
    is_subscription: false,
    is_active: true,
  })
  const [createProduct, { isLoading, error }] = useCreateProductMutation()
  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) =>
    setForm((f) => ({
      ...f,
      [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value,
    }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      await createProduct(form).unwrap()
      onClose()
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <Modal title="Add Product" subtitle="Creates a catalog item for this company" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        <TextField
          label="Product name"
          value={form.name}
          onChange={update('name')}
          error={fieldErrors.name}
          placeholder="Dell Latitude 5440"
          required
        />
        <div className="grid grid-cols-2 gap-4">
          <SelectField
            label="Category"
            value={form.category}
            onChange={update('category')}
            error={fieldErrors.category}
            options={CATEGORIES.map((c) => ({ value: c, label: c }))}
          />
          <TextField
            label="Base price (₹)"
            type="number"
            min="0"
            step="0.01"
            value={form.base_price}
            onChange={update('base_price')}
            error={fieldErrors.base_price}
            placeholder="80000"
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <TextField label="Unit" value={form.unit} onChange={update('unit')} error={fieldErrors.unit} />
          <TextField
            label="Tax %"
            type="number"
            min="0"
            step="0.01"
            value={form.tax_pct}
            onChange={update('tax_pct')}
            error={fieldErrors.tax_pct}
          />
        </div>
        <TextField
          label="Description"
          value={form.description}
          onChange={update('description')}
          error={fieldErrors.description}
          placeholder="Optional"
        />
        <div className="flex gap-6 pt-1">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.is_subscription}
              onChange={update('is_subscription')}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Recurring / subscription
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={update('is_active')}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Active
          </label>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {isLoading ? 'Saving…' : 'Add Product'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function AddVariantModal({ products, onClose }) {
  const [form, setForm] = useState({
    productId: products[0]?.id ?? '',
    attribute: '',
    value: '',
    extra_price: '0',
  })
  const [createVariant, { isLoading, error }] = useCreateVariantMutation()
  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      await createVariant(form).unwrap()
      onClose()
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <Modal title="Add Variant" subtitle="e.g. RAM: 16GB (+₹8,000)" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        <SelectField
          label="Product"
          value={form.productId}
          onChange={update('productId')}
          options={products.map((p) => ({ value: p.id, label: p.name }))}
        />
        <div className="grid grid-cols-2 gap-4">
          <TextField
            label="Attribute"
            value={form.attribute}
            onChange={update('attribute')}
            error={fieldErrors.attribute}
            placeholder="RAM"
            required
          />
          <TextField
            label="Value"
            value={form.value}
            onChange={update('value')}
            error={fieldErrors.value}
            placeholder="16GB"
            required
          />
        </div>
        <TextField
          label="Extra price (₹)"
          type="number"
          step="0.01"
          value={form.extra_price}
          onChange={update('extra_price')}
          error={fieldErrors.extra_price}
        />
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {isLoading ? 'Saving…' : 'Add Variant'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function AddPriceListModal({ onClose }) {
  const [form, setForm] = useState({ name: '', currency: 'INR' })
  const [createPriceList, { isLoading, error }] = useCreatePriceListMutation()
  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      await createPriceList(form).unwrap()
      onClose()
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <Modal title="New Price List" subtitle="A named price book, e.g. “APAC, USD”" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        <TextField
          label="Name"
          value={form.name}
          onChange={update('name')}
          error={fieldErrors.name}
          placeholder="India, INR"
          required
        />
        <TextField
          label="Currency"
          value={form.currency}
          onChange={update('currency')}
          error={fieldErrors.currency}
          maxLength={3}
          required
        />
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {isLoading ? 'Saving…' : 'Create'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function ProductsPage() {
  const [tab, setTab] = useState(TABS[0])
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)

  const { data: products = [], isLoading, error } = useGetProductsQuery(search || undefined)
  const { data: priceLists = [] } = useGetPriceListsQuery(undefined, {
    skip: tab !== 'Price Lists',
  })

  const categories = useMemo(() => {
    const map = new Map()
    for (const product of products) {
      const row = map.get(product.category) ?? { category: product.category, count: 0, active: 0 }
      row.count += 1
      if (product.is_active) row.active += 1
      map.set(product.category, row)
    }
    return [...map.values()].sort((a, b) => b.count - a.count)
  }, [products])

  const variants = useMemo(
    () =>
      products.flatMap((product) =>
        (product.variants ?? []).map((variant) => ({ ...variant, product_name: product.name })),
      ),
    [products],
  )

  const { formError } = parseApiError(error)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Products</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Catalog, price books and variants for your company.
          </p>
        </div>
        <button
          onClick={() =>
            setModal(tab === 'Price Lists' ? 'price-list' : tab === 'Variants' ? 'variant' : 'product')
          }
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          {tab === 'Price Lists' ? '+ Add Price List' : tab === 'Variants' ? '+ Add Variant' : '+ Add Product'}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-4 border-b border-slate-200">
        {TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`-mb-px border-b-2 px-1 pb-2.5 text-sm transition ${
              tab === item
                ? 'border-brand-600 font-medium text-brand-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {formError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {formError}
        </div>
      )}

      {tab === 'All Products' && (
        <>
          <div className="relative max-w-sm">
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

          <Card>
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <Th>Name</Th>
                  <Th>Category</Th>
                  <Th className="text-right">Base Price</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && <EmptyRow colSpan={4}>Loading products…</EmptyRow>}
                {!isLoading && products.length === 0 && (
                  <EmptyRow colSpan={4}>No products yet. Use “+ Add Product” to create one.</EmptyRow>
                )}
                {products.map((product) => (
                  <tr key={product.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold ${
                            CATEGORY_TINT[product.category] ?? 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {product.name.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{product.name}</p>
                          {product.is_subscription && (
                            <p className="text-xs text-amber-600">Recurring</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{product.category}</td>
                    <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                      {formatCurrency(product.base_price)}
                    </td>
                    <td className="px-5 py-3">
                      <StatusPill active={product.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      {tab === 'Price Lists' && (
        <Card>
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <Th>Name</Th>
                <Th>Currency</Th>
                <Th className="text-right">Price Rows</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {priceLists.length === 0 && <EmptyRow colSpan={3}>No price lists yet.</EmptyRow>}
              {priceLists.map((list) => (
                <tr key={list.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 text-sm font-medium text-slate-900">{list.name}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{list.currency}</td>
                  <td className="px-5 py-3 text-right text-sm text-slate-600">{list.item_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {tab === 'Categories' && (
        <Card>
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <Th>Category</Th>
                <Th className="text-right">Products</Th>
                <Th className="text-right">Active</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {categories.length === 0 && <EmptyRow colSpan={3}>No products yet.</EmptyRow>}
              {categories.map((row) => (
                <tr key={row.category} className="hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <span
                      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${
                        CATEGORY_TINT[row.category] ?? 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {row.category}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right text-sm text-slate-600">{row.count}</td>
                  <td className="px-5 py-3 text-right text-sm text-slate-600">{row.active}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {tab === 'Variants' && (
        <Card>
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <Th>Product</Th>
                <Th>Attribute</Th>
                <Th>Value</Th>
                <Th className="text-right">Extra Price</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {variants.length === 0 && <EmptyRow colSpan={4}>No variants yet.</EmptyRow>}
              {variants.map((variant) => (
                <tr key={variant.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 text-sm font-medium text-slate-900">
                    {variant.product_name}
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600">{variant.attribute}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{variant.value}</td>
                  <td className="px-5 py-3 text-right text-sm text-slate-600">
                    {Number(variant.extra_price) > 0 ? `+ ${formatCurrency(variant.extra_price)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {modal === 'product' && <AddProductModal onClose={() => setModal(null)} />}
      {modal === 'variant' && <AddVariantModal products={products} onClose={() => setModal(null)} />}
      {modal === 'price-list' && <AddPriceListModal onClose={() => setModal(null)} />}
    </div>
  )
}
