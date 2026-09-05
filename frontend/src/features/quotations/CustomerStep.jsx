import { useState } from 'react'

import { parseApiError } from '../../shared/api/errors'
import Modal from '../../shared/ui/Modal'
import SelectField from '../../shared/ui/SelectField'
import StatusPill from '../../shared/ui/StatusPill'
import TextField from '../../shared/ui/TextField'
import { useCreateCustomerMutation, useGetCustomersQuery } from './quotationsApi'

function initials(name) {
  return name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function AddCustomerModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', email: '', tier: 'Bronze', location: '', password: '' })
  const [createCustomer, { isLoading, error }] = useCreateCustomerMutation()
  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      const customer = await createCustomer(form).unwrap()
      onCreated(customer)
      onClose()
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <Modal title="Add New Customer" subtitle="Tier drives the discount ceiling" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}
        <TextField
          label="Customer name"
          value={form.name}
          onChange={update('name')}
          error={fieldErrors.name}
          placeholder="Acme Technologies Pvt Ltd"
          required
        />
        <TextField
          label="Email"
          type="email"
          value={form.email}
          onChange={update('email')}
          error={fieldErrors.email}
          placeholder="procurement@acmetech.example"
          required
        />
        <div className="grid grid-cols-2 gap-4">
          <SelectField
            label="Tier"
            value={form.tier}
            onChange={update('tier')}
            error={fieldErrors.tier}
            options={['Bronze', 'Silver', 'Gold'].map((t) => ({ value: t, label: t }))}
          />
          <TextField
            label="Location"
            value={form.location}
            onChange={update('location')}
            error={fieldErrors.location}
            placeholder="Mumbai, India"
          />
        </div>
        <TextField
          label="Portal password (optional)"
          type="password"
          value={form.password}
          onChange={update('password')}
          error={fieldErrors.password}
          placeholder="Leave blank to only allow the emailed magic link"
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
            {isLoading ? 'Saving…' : 'Add Customer'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function CustomerStep({ selectedId, onSelect, error }) {
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const { data: customers = [], isLoading } = useGetCustomersQuery(search || undefined)

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-slate-900">Select Customer</h2>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <svg viewBox="0 0 24 24" className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email or company..."
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="rounded-lg border border-brand-600 px-3.5 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
        >
          + Add New Customer
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Name</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Email</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Tier</th>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Location</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-500">
                  Loading customers…
                </td>
              </tr>
            )}
            {!isLoading && customers.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-500">
                  No customers match that search.
                </td>
              </tr>
            )}
            {customers.map((customer) => {
              const isSelected = customer.id === selectedId
              return (
                <tr key={customer.id} className={isSelected ? 'bg-brand-50' : 'hover:bg-slate-50'}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-600">
                        {initials(customer.name)}
                      </span>
                      <span className="text-sm font-medium text-slate-900">{customer.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600">{customer.email}</td>
                  <td className="px-5 py-3">
                    <StatusPill value={customer.tier} label={customer.tier} />
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600">{customer.location || '—'}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => onSelect(customer)}
                      className={`rounded-md px-3 py-1 text-xs font-medium ${
                        isSelected
                          ? 'bg-brand-600 text-white'
                          : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {isSelected ? 'Selected' : 'Select'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {showModal && (
        <AddCustomerModal onClose={() => setShowModal(false)} onCreated={onSelect} />
      )}
    </div>
  )
}
