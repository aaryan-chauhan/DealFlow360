import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { Link, useNavigate } from 'react-router-dom'

import { parseApiError } from '../shared/api/errors'
import TextField from '../shared/ui/TextField'
import BrandPanel from './BrandPanel'
import { useSignupMutation } from './authApi'
import { credentialsReceived } from './authSlice'

export default function SignupPage() {
  const [form, setForm] = useState({
    full_name: '',
    company_name: '',
    email: '',
    password: '',
  })
  const [signup, { isLoading, error }] = useSignupMutation()
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    try {
      const data = await signup(form).unwrap()
      dispatch(credentialsReceived({ ...data, remember: true }))
      navigate('/dashboard', { replace: true })
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <BrandPanel />

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
          <p className="mt-1 text-sm text-slate-500">
            Set up your company workspace — you&apos;ll be its first Admin.
          </p>

          <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
            {formError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {formError}
              </div>
            )}

            <TextField
              label="Full name"
              name="full_name"
              autoComplete="name"
              placeholder="Aaryan Chauhan"
              value={form.full_name}
              onChange={update('full_name')}
              error={fieldErrors.full_name}
              required
            />

            <TextField
              label="Company name"
              name="company_name"
              autoComplete="organization"
              placeholder="Acme Solutions"
              value={form.company_name}
              onChange={update('company_name')}
              error={fieldErrors.company_name}
              required
            />

            <TextField
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              placeholder="aaryan@company.com"
              value={form.email}
              onChange={update('email')}
              error={fieldErrors.email}
              required
            />

            <TextField
              label="Password"
              type="password"
              name="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={update('password')}
              error={fieldErrors.password}
              required
            />

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="mt-7 text-center text-sm text-slate-600">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Sign in
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
