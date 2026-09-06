import { useState } from 'react'

import { parseApiError } from '../../shared/api/errors'
import { formatCurrency } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import SelectField from '../../shared/ui/SelectField'
import TextField from '../../shared/ui/TextField'
import { useGetProductsQuery } from './catalogApi'
import {
  useCreateUpsellRuleMutation,
  useDeleteUpsellRuleMutation,
  useGetUpsellRulesQuery,
  useUpdateUpsellRuleMutation,
} from './upsellApi'

function FormModal({ title, onClose, onSubmit, isLoading, error, children }) {
  const { formError } = parseApiError(error)
  return (
    <Modal
      title={title}
      subtitle="Rules the Upsell & Cross-sell panel reads from while a rep is building a quote."
      onClose={onClose}
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        {children}
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
            {isLoading ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function RuleModal({ rule, products, onClose }) {
  const isEdit = Boolean(rule)
  const [form, setForm] = useState({
    source_product: rule?.source_product ?? '',
    recommended_product: rule?.recommended_product ?? '',
    co_purchase_score: rule ? String(parseFloat(rule.co_purchase_score)) : '50',
    min_margin_pct: rule ? String(parseFloat(rule.min_margin_pct)) : '15',
    is_promoted: rule?.is_promoted ?? false,
  })
  const [create, createState] = useCreateUpsellRuleMutation()
  const [update, updateState] = useUpdateUpsellRuleMutation()
  const { isLoading, error } = isEdit ? updateState : createState
  const { fieldErrors } = parseApiError(error)

  const productOptions = products.map((p) => ({ value: p.id, label: `${p.name} (${p.category})` }))

  async function submit(event) {
    event.preventDefault()
    const body = {
      source_product: form.source_product,
      recommended_product: form.recommended_product,
      co_purchase_score: form.co_purchase_score,
      min_margin_pct: form.min_margin_pct,
      is_promoted: form.is_promoted,
    }
    try {
      if (isEdit) {
        await update({ id: rule.id, ...body }).unwrap()
      } else {
        await create(body).unwrap()
      }
      onClose()
    } catch {
      /* surfaced above */
    }
  }

  return (
    <FormModal
      title={isEdit ? 'Edit upsell rule' : 'New upsell rule'}
      onClose={onClose}
      onSubmit={submit}
      isLoading={isLoading}
      error={error}
    >
      <SelectField
        label="When this product is in the cart…"
        options={[{ value: '', label: 'Select a product' }, ...productOptions]}
        value={form.source_product}
        onChange={(e) => setForm({ ...form, source_product: e.target.value })}
        error={fieldErrors.source_product}
        required
      />
      <SelectField
        label="…recommend this product"
        options={[{ value: '', label: 'Select a product' }, ...productOptions]}
        value={form.recommended_product}
        onChange={(e) => setForm({ ...form, recommended_product: e.target.value })}
        error={fieldErrors.recommended_product}
        required
      />
      <div className="grid grid-cols-2 gap-4">
        <TextField
          label="Co-purchase score (0-100)"
          type="number"
          min="0"
          max="100"
          step="1"
          value={form.co_purchase_score}
          onChange={(e) => setForm({ ...form, co_purchase_score: e.target.value })}
          error={fieldErrors.co_purchase_score}
        />
        <TextField
          label="Min margin % to show"
          type="number"
          min="0"
          max="100"
          step="1"
          value={form.min_margin_pct}
          onChange={(e) => setForm({ ...form, min_margin_pct: e.target.value })}
          error={fieldErrors.min_margin_pct}
        />
      </div>
      <label className="flex items-center gap-2.5 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={form.is_promoted}
          onChange={(e) => setForm({ ...form, is_promoted: e.target.checked })}
          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
        />
        Active promotion — ranks above co-purchase score and shows a "Promo" tag
      </label>
    </FormModal>
  )
}

export default function UpsellRulesPage() {
  const { data: rules = [], isLoading } = useGetUpsellRulesQuery()
  const { data: products = [] } = useGetProductsQuery()
  const [deleteRule] = useDeleteUpsellRuleMutation()
  const [modalRule, setModalRule] = useState(null)
  const [showModal, setShowModal] = useState(false)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Upsell &amp; Cross-sell Rules</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Pair products so the Upsell panel on a quotation has something to recommend. No
            rules for a product means no suggestions ever appear for it (§7.4).
          </p>
        </div>
        <button
          onClick={() => {
            setModalRule(null)
            setShowModal(true)
          }}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        >
          + New Rule
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              {['Source Product', 'Recommends', 'Co-purchase Score', 'Min Margin', 'Promoted', ''].map(
                (heading) => (
                  <th
                    key={heading}
                    className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500"
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
                <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading rules…
                </td>
              </tr>
            )}
            {!isLoading && rules.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                  No upsell rules yet — nothing will be recommended on any quotation until you add
                  one.
                </td>
              </tr>
            )}
            {rules.map((rule) => (
              <tr key={rule.id} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-sm font-medium text-slate-900">
                  {rule.source_product_name}
                </td>
                <td className="px-5 py-3 text-sm text-slate-700">{rule.recommended_product_name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {parseFloat(rule.co_purchase_score)}%
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">
                  {parseFloat(rule.min_margin_pct)}%
                </td>
                <td className="px-5 py-3">
                  {rule.is_promoted ? (
                    <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                      Promoted
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => {
                        setModalRule(rule)
                        setShowModal(true)
                      }}
                      className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => deleteRule(rule.id)}
                      className="rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <RuleModal rule={modalRule} products={products} onClose={() => setShowModal(false)} />
      )}
    </div>
  )
}
