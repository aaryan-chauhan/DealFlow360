import { useState } from 'react'
import { useSelector } from 'react-redux'

import { selectActiveRole } from '../../auth/authSlice'
import {
  useCreateWarehouseMutation,
  useGetStockLevelsQuery,
  useGetWarehousesQuery,
  useUpdateStockLevelMutation,
} from './adminApi'

// Mirrors backend/warehouses_fulfillment/views.py's MANAGE_ROLES — Finance & Admin
// manage warehouses/stock per spec §3; Sales Manager may view this screen but any
// write here would 403, so the controls stay hidden rather than offering an action
// that fails.
const MANAGE_ROLES = ['admin', 'finance_ops']

export default function WarehousesPage() {
  const role = useSelector(selectActiveRole)
  const canManage = MANAGE_ROLES.includes(role)
  const { data: warehouses = [], isLoading: loadingWarehouses } = useGetWarehousesQuery()
  const { data: stockLevels = [], isLoading: loadingStock } = useGetStockLevelsQuery()
  const [createWarehouse, { isLoading: isCreating }] = useCreateWarehouseMutation()
  const [updateStockLevel, { isLoading: isUpdatingStock }] = useUpdateStockLevelMutation()

  const [showAddModal, setShowAddModal] = useState(false)
  const [name, setName] = useState('')
  const [weight, setWeight] = useState('1.00')
  const [editingStockId, setEditingStockId] = useState(null)
  const [editingQty, setEditingQty] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  async function handleCreateWarehouse(e) {
    e.preventDefault()
    setErrorMsg('')
    try {
      await createWarehouse({
        name,
        shipping_cost_weight: weight,
        replenishment_rule: { lead_time_days: 7 },
      }).unwrap()
      setName('')
      setWeight('1.00')
      setShowAddModal(false)
    } catch (err) {
      setErrorMsg(err?.data?.detail || 'Failed to create warehouse')
    }
  }

  async function handleSaveStock(id) {
    try {
      await updateStockLevel({ id, qty_on_hand: editingQty }).unwrap()
      setEditingStockId(null)
    } catch (err) {
      alert(err?.data?.detail || 'Failed to update stock level')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Warehouses & Stock Inventory</h1>
          <p className="text-xs text-slate-500">Configure shipping locations and manage stock levels per SKU</p>
        </div>
        {canManage && (
          <button
            onClick={() => setShowAddModal(true)}
            className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 shadow transition"
          >
            + Add Warehouse
          </button>
        )}
      </div>

      {/* Warehouse Locations Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loadingWarehouses ? (
          <p className="text-sm text-slate-500">Loading warehouses...</p>
        ) : (
          warehouses.map((wh) => (
            <div key={wh.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">{wh.name}</h3>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                  Weight: {wh.shipping_cost_weight}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Preferred rank: {parseFloat(wh.shipping_cost_weight) <= 1 ? '1st (Primary / Cheapest)' : 'Secondary Depot'}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Stock Levels Matrix Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">Live Inventory Stock Levels</h2>
        <p className="text-xs text-slate-500 mb-4">Stock on hand, reserved quantities, and available stock per product</p>

        {loadingStock ? (
          <p className="text-sm text-slate-500">Loading stock levels...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3">Product Name</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Qty On Hand</th>
                  <th className="px-4 py-3">Qty Reserved</th>
                  <th className="px-4 py-3">Available</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stockLevels.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-500">
                      No stock records found. Run seed commands or select products.
                    </td>
                  </tr>
                )}
                {stockLevels.map((st) => (
                  <tr key={st.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-medium text-slate-900">{st.warehouse_name}</td>
                    <td className="px-4 py-3">{st.product_name}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{st.product_category}</td>
                    <td className="px-4 py-3 font-semibold text-slate-900">
                      {editingStockId === st.id ? (
                        <input
                          type="number"
                          value={editingQty}
                          onChange={(e) => setEditingQty(e.target.value)}
                          className="w-24 rounded border border-slate-300 px-2 py-1 text-sm outline-none focus:border-brand-600"
                        />
                      ) : (
                        st.qty_on_hand
                      )}
                    </td>
                    <td className="px-4 py-3 text-amber-600 font-medium">{st.qty_reserved}</td>
                    <td className="px-4 py-3 text-emerald-600 font-bold">{st.qty_available}</td>
                    <td className="px-4 py-3 text-right">
                      {!canManage ? (
                        <span className="text-xs text-slate-400">View only</span>
                      ) : editingStockId === st.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleSaveStock(st.id)}
                            disabled={isUpdatingStock}
                            className="rounded bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-500"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setEditingStockId(null)}
                            className="rounded bg-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-300"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingStockId(st.id)
                            setEditingQty(st.qty_on_hand)
                          }}
                          className="text-xs font-semibold text-brand-600 hover:underline"
                        >
                          Update Stock
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Warehouse Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Add New Warehouse</h2>
            {errorMsg && <p className="text-xs font-medium text-rose-600">{errorMsg}</p>}
            <form onSubmit={handleCreateWarehouse} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700">Warehouse Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. West Coast Depot"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Shipping Cost Weight</label>
                <input
                  type="number"
                  step="0.1"
                  required
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600"
                />
                <p className="mt-1 text-[11px] text-slate-400">Lower numbers (e.g. 1.0) indicate preferred cheaper fulfillment sites.</p>
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
                  {isCreating ? 'Saving...' : 'Create Warehouse'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
