import { useEffect, useState } from 'react'

import { parseApiError } from '../../shared/api/errors'
import { formatPct } from '../../shared/format'
import Modal from '../../shared/ui/Modal'
import SelectField from '../../shared/ui/SelectField'
import TextField from '../../shared/ui/TextField'
import {
  useCreateApprovalChainMutation,
  useCreateCategoryCeilingMutation,
  useCreateDiscountTierMutation,
  useGetApprovalChainsQuery,
  useGetDiscountTiersQuery,
  useUpdateApprovalChainMutation,
  useUpdateCategoryCeilingMutation,
  useUpdateDiscountTierMutation,
} from './pricingApi'

const CATEGORIES = ['Hardware', 'Software', 'Services', 'Subscription']
const LEVELS = [
  { value: 'none', label: 'No approval' },
  { value: 'manager', label: 'Sales Manager' },
  { value: 'manager_then_finance', label: 'Sales Manager → Finance' },
]

function Card({ title, action, children }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Th({ children, className = '' }) {
  return (
    <th className={`px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 ${className}`}>
      {children}
    </th>
  )
}

function EditButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
    >
      Edit
    </button>
  )
}

function FormModal({ title, subtitle, onClose, onSubmit, isLoading, error, children }) {
  const { formError } = parseApiError(error)
  return (
    <Modal title={title} subtitle={subtitle} onClose={onClose}>
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

function TierModal({ tier, onClose }) {
  const [form, setForm] = useState({
    name: tier?.name ?? '',
    max_discount_pct: tier?.max_discount_pct ?? '',
  })
  const [createTier, createState] = useCreateDiscountTierMutation()
  const [updateTier, updateState] = useUpdateDiscountTierMutation()
  const state = tier ? updateState : createState
  const { fieldErrors } = parseApiError(state.error)

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      if (tier) await updateTier({ id: tier.id, ...form }).unwrap()
      else await createTier(form).unwrap()
      onClose()
    } catch {
      /* surfaced through `state.error` */
    }
  }

  return (
    <FormModal
      title={tier ? `Edit ${tier.name}` : 'Add Discount Tier'}
      subtitle="The overall ceiling for this customer tier"
      onClose={onClose}
      onSubmit={handleSubmit}
      isLoading={state.isLoading}
      error={state.error}
    >
      <TextField
        label="Customer tier"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        error={fieldErrors.name}
        placeholder="Gold"
        required
      />
      <TextField
        label="Max discount %"
        type="number"
        min="0"
        max="100"
        step="0.01"
        value={form.max_discount_pct}
        onChange={(e) => setForm((f) => ({ ...f, max_discount_pct: e.target.value }))}
        error={fieldErrors.max_discount_pct}
        required
      />
    </FormModal>
  )
}

function CeilingModal({ tier, ceiling, onClose }) {
  const [form, setForm] = useState({
    category: ceiling?.category ?? CATEGORIES[0],
    max_discount_pct: ceiling?.max_discount_pct ?? '',
  })
  const [createCeiling, createState] = useCreateCategoryCeilingMutation()
  const [updateCeiling, updateState] = useUpdateCategoryCeilingMutation()
  const state = ceiling ? updateState : createState
  const { fieldErrors } = parseApiError(state.error)

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      if (ceiling) await updateCeiling({ id: ceiling.id, ...form }).unwrap()
      else await createCeiling({ discount_tier: tier.id, ...form }).unwrap()
      onClose()
    } catch {
      /* surfaced through `state.error` */
    }
  }

  return (
    <FormModal
      title={ceiling ? `Edit ${ceiling.category} rule` : 'Add Category Rule'}
      subtitle={`Stricter override inside the ${tier.name} tier — the effective cap is the lower of the two`}
      onClose={onClose}
      onSubmit={handleSubmit}
      isLoading={state.isLoading}
      error={state.error}
    >
      <SelectField
        label="Category"
        value={form.category}
        onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
        error={fieldErrors.category}
        options={CATEGORIES.map((c) => ({ value: c, label: c }))}
        disabled={Boolean(ceiling)}
      />
      <TextField
        label="Max discount %"
        type="number"
        min="0"
        max="100"
        step="0.01"
        value={form.max_discount_pct}
        onChange={(e) => setForm((f) => ({ ...f, max_discount_pct: e.target.value }))}
        error={fieldErrors.max_discount_pct}
        required
      />
    </FormModal>
  )
}

function ChainModal({ rule, onClose }) {
  const [form, setForm] = useState({
    discount_range_from: rule?.discount_range_from ?? '',
    discount_range_to: rule?.discount_range_to ?? '',
    required_level: rule?.required_level ?? 'manager',
  })
  const [createChain, createState] = useCreateApprovalChainMutation()
  const [updateChain, updateState] = useUpdateApprovalChainMutation()
  const state = rule ? updateState : createState
  const { fieldErrors } = parseApiError(state.error)

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      if (rule) await updateChain({ id: rule.id, ...form }).unwrap()
      else await createChain(form).unwrap()
      onClose()
    } catch {
      /* surfaced through `state.error` */
    }
  }

  return (
    <FormModal
      title={rule ? 'Edit Approval Rule' : 'Add Approval Rule'}
      subtitle="Routing score range → who must approve. Ranges are half-open [from, to)."
      onClose={onClose}
      onSubmit={handleSubmit}
      isLoading={state.isLoading}
      error={state.error}
    >
      <div className="grid grid-cols-2 gap-4">
        <TextField
          label="Range from"
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={form.discount_range_from}
          onChange={(e) => setForm((f) => ({ ...f, discount_range_from: e.target.value }))}
          error={fieldErrors.discount_range_from}
          required
        />
        <TextField
          label="Range to"
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={form.discount_range_to}
          onChange={(e) => setForm((f) => ({ ...f, discount_range_to: e.target.value }))}
          error={fieldErrors.discount_range_to}
          required
        />
      </div>
      <SelectField
        label="Required approval"
        value={form.required_level}
        onChange={(e) => setForm((f) => ({ ...f, required_level: e.target.value }))}
        error={fieldErrors.required_level}
        options={LEVELS}
      />
    </FormModal>
  )
}

export default function DiscountConfigPage() {
  const { data: tiers = [], isLoading, error } = useGetDiscountTiersQuery()
  const { data: chains = [] } = useGetApprovalChainsQuery()
  const [selectedTierId, setSelectedTierId] = useState(null)
  const [modal, setModal] = useState(null)

  useEffect(() => {
    if (!selectedTierId && tiers.length) setSelectedTierId(tiers[0].id)
  }, [tiers, selectedTierId])

  const selectedTier = tiers.find((t) => t.id === selectedTierId) ?? tiers[0] ?? null
  const { formError } = parseApiError(error)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Discount Tiers & Approval Chains</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Governance rules the risk engine reads on every quotation line.
        </p>
      </div>

      {formError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {formError}
        </div>
      )}

      <Card
        title="Discount Tiers"
        action={
          <button
            onClick={() => setModal({ type: 'tier' })}
            className="rounded-lg bg-brand-600 px-3.5 py-1.5 text-sm font-semibold text-white hover:bg-brand-700"
          >
            + Add Tier
          </button>
        }
      >
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <Th>Customer Tier</Th>
              <Th className="text-right">Max Discount</Th>
              <Th>Approval Chain</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading tiers…
                </td>
              </tr>
            )}
            {!isLoading && tiers.length === 0 && (
              <tr>
                <td colSpan={4} className="px-5 py-10 text-center text-sm text-slate-500">
                  No tiers configured yet.
                </td>
              </tr>
            )}
            {tiers.map((tier) => (
              <tr key={tier.id} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-sm font-medium text-slate-900">{tier.name}</td>
                <td className="px-5 py-3 text-right text-sm font-medium text-slate-900">
                  {formatPct(tier.max_discount_pct)}
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">{tier.approval_chain?.label}</td>
                <td className="px-5 py-3 text-right">
                  <EditButton onClick={() => setModal({ type: 'tier', tier })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card
        title="Category Specific Rules"
        action={
          <div className="flex items-center gap-2">
            <select
              value={selectedTier?.id ?? ''}
              onChange={(e) => setSelectedTierId(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-brand-600"
            >
              {tiers.map((tier) => (
                <option key={tier.id} value={tier.id}>
                  {tier.name} tier
                </option>
              ))}
            </select>
            <button
              onClick={() => setModal({ type: 'ceiling', tier: selectedTier })}
              disabled={!selectedTier}
              className="rounded-lg border border-slate-300 px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              + Add Rule
            </button>
          </div>
        }
      >
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <Th>Category</Th>
              <Th className="text-right">Max Discount</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(selectedTier?.category_ceilings ?? []).length === 0 && (
              <tr>
                <td colSpan={3} className="px-5 py-10 text-center text-sm text-slate-500">
                  No category overrides for this tier.
                </td>
              </tr>
            )}
            {(selectedTier?.category_ceilings ?? []).map((ceiling) => (
              <tr key={ceiling.id} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-sm font-medium text-slate-900">{ceiling.category}</td>
                <td className="px-5 py-3 text-right text-sm text-slate-900">
                  {formatPct(ceiling.max_discount_pct)}
                </td>
                <td className="px-5 py-3 text-right">
                  <EditButton
                    onClick={() => setModal({ type: 'ceiling', tier: selectedTier, ceiling })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card
        title="Approval Chain Rules"
        action={
          <button
            onClick={() => setModal({ type: 'chain' })}
            className="rounded-lg border border-slate-300 px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            + Add Rule
          </button>
        }
      >
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <Th>Routing Score Range</Th>
              <Th>Required Approval</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {chains.length === 0 && (
              <tr>
                <td colSpan={3} className="px-5 py-10 text-center text-sm text-slate-500">
                  No approval chain rules configured.
                </td>
              </tr>
            )}
            {chains.map((rule) => (
              <tr key={rule.id} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-sm text-slate-900">
                  {formatPct(rule.discount_range_from)} – {formatPct(rule.discount_range_to)}
                </td>
                <td className="px-5 py-3 text-sm text-slate-600">{rule.required_level_display}</td>
                <td className="px-5 py-3 text-right">
                  <EditButton onClick={() => setModal({ type: 'chain', rule })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {modal?.type === 'tier' && <TierModal tier={modal.tier} onClose={() => setModal(null)} />}
      {modal?.type === 'ceiling' && (
        <CeilingModal tier={modal.tier} ceiling={modal.ceiling} onClose={() => setModal(null)} />
      )}
      {modal?.type === 'chain' && <ChainModal rule={modal.rule} onClose={() => setModal(null)} />}
    </div>
  )
}
