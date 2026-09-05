import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useLoginCustomerMutation } from './portalApi'

/** The customer's second way in (spec A1) — email + password, alongside a rep-sent
 *  magic link. On success this hands back a customer-scoped token (never a JWT, never
 *  workspace-wide — see `portalApi.js`) which then travels in the URL exactly like a
 *  quotation token does, rather than being persisted anywhere. */
export default function PortalLoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [login, { isLoading, error }] = useLoginCustomerMutation()
  const errorMessage = error
    ? error.status === 401
      ? 'Incorrect email or password.'
      : 'Something went wrong. Please try again.'
    : null

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      const result = await login({ email, password }).unwrap()
      navigate(`/portal/my-quotations/${result.customer_token}`)
    } catch {
      /* surfaced through `errorMessage` */
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-lg font-semibold text-slate-900">Customer Portal</h1>
      <p className="mt-1 text-sm text-slate-500">
        Log in to see all of your quotations, or open the link your account manager sent you.
      </p>

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        {errorMessage && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {errorMessage}
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-slate-700">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-4 focus:ring-brand-100"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {isLoading ? 'Logging in…' : 'Log In'}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-slate-400">
        No password set up yet? Ask your account manager for a portal link instead.
      </p>
    </div>
  )
}
