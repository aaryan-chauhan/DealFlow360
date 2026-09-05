import { useState } from 'react'
import { useGetProductsQuery } from './catalogApi'
import {
  useCreateUpsellRuleMutation,
  useDeleteUpsellRuleMutation,
  useGetUpsellRulesQuery,
} from './adminApi'

export default function UpsellRulesPage() {
  const { data: rules = [], isLoading: loadingRules } = useGetUpsellRulesQuery()
  const { data: products = [], isLoading: loadingProducts } = useGetProductsQuery()
  const [createRule, { isLoading: isCreating }] = useCreateUpsellRuleMutation()
  const [deleteRule] = useDeleteUpsellRuleMutation()

  const [showAddModal, setShowAddModal] = useState(false)
  const [sourceProduct, setSourceProduct] = useState('')
  const [recommendedProduct, setRecommendedProduct] = useState('')
  const [score, setScore] = useState('80.00')
  const [minMargin, setMinMargin] = useState('15.00')
  const [isPromoted, setIsPromoted] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  async function handleCreateRule(e) {
    e.preventDefault()
    setErrorMsg('')
    if (sourceProduct === recommendedProduct) {
      setErrorMsg('Source product and recommended product cannot be the same.')
      return
    }
    try {
      await createRule({
        source_product: sourceProduct,
        recommended_product: recommendedProduct,
        co_purchase_score: score,
        min_margin_pct: minMargin,
        is_promoted: isPromoted,
      }).unwrap()
      setShowAddModal(false)
    } catch (err) {
      setErrorMsg(err?.data?.detail || 'Failed to create upsell rule.')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Upsell & Cross-Sell Rules</h1>
          <p className="text-xs text-slate-500">Configure pairing recommendations, co-purchase scores, and minimum margin caps (spec §7.4)</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 shadow transition"
        >
          + Add Pairing Rule
        </button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {loadingRules ? (
          <p className="text-sm text-slate-500">Loading upsell rules...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Source Product (In Cart)</th>
                  <th className="px-4 py-3">Recommended Product</th>
                  <th className="px-4 py-3">Co-Purchase Score</th>
                  <th className="px-4 py-3">Min. Margin Cap</th>
                  <th className="px-4 py-3">Promoted</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-xs text-slate-500">
                      No upsell rules configured. Click Add Pairing Rule or run seed_all.
                    </td>
                  </tr>
                )}
                {rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-semibold text-slate-900">{rule.source_product_name}</td>
                    <td className="px-4 py-3 font-medium text-brand-600">➔ {rule.recommended_product_name}</td>
                    <td className="px-4 py-3 font-semibold text-slate-800">{rule.co_purchase_score}%</td>
                    <td className="px-4 py-3 text-emerald-600 font-medium">≥ {rule.min_margin_pct}%</td>
                    <td className="px-4 py-3">
                      {rule.is_promoted ? (
                        <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700 border border-indigo-200">
                          Promoted
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">Standard</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => deleteRule(rule.id)}
                        className="text-xs font-semibold text-slate-400 hover:text-rose-600"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Add Cross-Sell Pairing Rule</h2>
            {errorMsg && <p className="text-xs font-medium text-rose-600">{errorMsg}</p>}
            <form onSubmit={handleCreateRule} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Source Product (Item in Cart)</label>
                <select
                  required
                  value={sourceProduct}
                  onChange={(e) => setSourceProduct(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                >
                  <option value="">Select source product...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.category})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Recommended Product (Suggested Add-on)</label>
                <select
                  required
                  value={recommendedProduct}
                  onChange={(e) => setRecommendedProduct(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                >
                  <option value="">Select recommended product...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.category})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700">Co-Purchase Score (%)</label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700">Min Margin Cap (%)</label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    value={minMargin}
                    onChange={(e) => setMinMargin(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="promoted"
                  checked={isPromoted}
                  onChange={(e) => setIsPromoted(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <label htmlFor="promoted" className="text-xs font-medium text-slate-700">
                  Promote rule (Highlight first in recommendation drawer)
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="rounded-xl bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-500"
                >
                  {isCreating ? 'Saving...' : 'Save Pairing Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
