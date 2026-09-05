import { useState } from 'react'
import { useSelector } from 'react-redux'

import { selectActiveRole } from '../../auth/authSlice'
import { useCreateSubscriptionPlanMutation, useGetSubscriptionPlansQuery } from './adminApi'

export default function SubscriptionPlansPage() {
  // Mirrors backend's IsAdminOrReadOnly on SubscriptionPlanViewSet — Admin-only
  // config per spec §5.8; Finance may view this screen for billing context but
  // any write here would 403, so the control stays hidden for that role.
  const canManage = useSelector(selectActiveRole) === 'admin'
  const { data: plans = [], isLoading } = useGetSubscriptionPlansQuery()
  const [createPlan, { isLoading: isCreating }] = useCreateSubscriptionPlanMutation()

  const [showAddModal, setShowAddModal] = useState(false)
  const [name, setName] = useState('')
  const [cycle, setCycle] = useState('Monthly')
  const [prorationMode, setProrationMode] = useState('daily')
  const [refundType, setRefundType] = useState('prorated_refund')
  const [errorMsg, setErrorMsg] = useState('')

  async function handleCreatePlan(e) {
    e.preventDefault()
    setErrorMsg('')
    try {
      await createPlan({
        name,
        cycle,
        proration_rule: { mode: prorationMode },
        cancellation_rule: { type: refundType },
        is_active: true,
      }).unwrap()
      setName('')
      setShowAddModal(false)
    } catch (err) {
      setErrorMsg(err?.data?.detail || 'Failed to create subscription plan')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Subscription Plans</h1>
          <p className="text-xs text-slate-500">Configure recurring billing cycles, proration rules, and cancellation refund policies</p>
        </div>
        {canManage && (
          <button
            onClick={() => setShowAddModal(true)}
            className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 shadow transition"
          >
            + Add Subscription Plan
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          <p className="text-sm text-slate-500">Loading plans...</p>
        ) : (
          plans.map((plan) => (
            <div key={plan.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">{plan.name}</h3>
                <span className="rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">
                  {plan.cycle}
                </span>
              </div>

              <div className="space-y-1 text-xs text-slate-600">
                <p>
                  <span className="font-medium text-slate-500">Proration Rule:</span>{' '}
                  <span className="font-semibold text-slate-800">{plan.proration_rule?.mode === 'none' ? 'No Proration' : 'Daily Pro-rata'}</span>
                </p>
                <p>
                  <span className="font-medium text-slate-500">Cancellation Policy:</span>{' '}
                  <span className="font-semibold text-slate-800 uppercase">{plan.cancellation_rule?.type || 'no_refund'}</span>
                </p>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className={`font-semibold ${plan.is_active ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {plan.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add Plan Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-900">New Subscription Plan Template</h2>
            {errorMsg && <p className="text-xs font-medium text-rose-600">{errorMsg}</p>}
            <form onSubmit={handleCreatePlan} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Plan Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Enterprise Support 1-Year"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Billing Cycle</label>
                <select
                  value={cycle}
                  onChange={(e) => setCycle(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                >
                  <option value="Monthly">Monthly</option>
                  <option value="Quarterly">Quarterly</option>
                  <option value="Yearly">Yearly</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Mid-Cycle Proration Rule</label>
                <select
                  value={prorationMode}
                  onChange={(e) => setProrationMode(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                >
                  <option value="daily">Daily Pro-rata Adjustment (§7.3.2)</option>
                  <option value="none">No Mid-Cycle Adjustment</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Cancellation Refund Policy</label>
                <select
                  value={refundType}
                  onChange={(e) => setRefundType(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                >
                  <option value="prorated_refund">Prorated Refund (Issue Credit Note)</option>
                  <option value="full_refund">Full Refund</option>
                  <option value="no_refund">No Refund</option>
                </select>
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
                  {isCreating ? 'Saving...' : 'Create Plan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
