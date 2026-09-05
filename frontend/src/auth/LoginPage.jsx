import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { parseApiError } from '../shared/api/errors'
import TextField from '../shared/ui/TextField'
import BrandPanel from './BrandPanel'
import { useLoginMutation } from './authApi'
import { credentialsReceived } from './authSlice'

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [remember, setRemember] = useState(true)
  const [notice, setNotice] = useState(null)
  const [login, { isLoading, error }] = useLoginMutation()
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()

  const { formError, fieldErrors } = parseApiError(error)
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setNotice(null)
    try {
      const data = await login(form).unwrap()
      dispatch(credentialsReceived({ ...data, remember }))
      navigate(location.state?.from ?? '/dashboard', { replace: true })
    } catch {
      /* surfaced through `error` */
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <BrandPanel />

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold text-slate-900">Welcome Back</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to your account</p>

          <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
            {formError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {formError}
              </div>
            )}

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
              autoComplete="current-password"
              placeholder="••••••••"
              value={form.password}
              onChange={update('password')}
              error={fieldErrors.password}
              required
            />

            <div className="flex items-center justify-between pt-0.5">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                Remember me
              </label>
              <button
                type="button"
                onClick={() => setNotice('Password reset lands with the notification phase.')}
                className="text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? 'Signing in…' : 'Sign In'}
            </button>

            <div className="flex items-center gap-3 py-1">
              <span className="h-px flex-1 bg-slate-200" />
              <span className="text-xs text-slate-400">or</span>
              <span className="h-px flex-1 bg-slate-200" />
            </div>

            <button
              type="button"
              onClick={() => setNotice('Google sign-in is not wired up yet.')}
              className="flex w-full items-center justify-center gap-2.5 rounded-lg border border-slate-300 bg-white py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4">
                <path fill="#4285F4" d="M23 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.2a5.3 5.3 0 0 1-2.3 3.5v2.9h3.7c2.2-2 3.4-5 3.4-8.6Z" />
                <path fill="#34A853" d="M12 23.5c3.1 0 5.7-1 7.6-2.8l-3.7-2.9c-1 .7-2.3 1.1-3.9 1.1-3 0-5.5-2-6.4-4.7H1.8v3A11.5 11.5 0 0 0 12 23.5Z" />
                <path fill="#FBBC05" d="M5.6 14.2a6.9 6.9 0 0 1 0-4.4v-3H1.8a11.5 11.5 0 0 0 0 10.4l3.8-3Z" />
                <path fill="#EA4335" d="M12 5.4c1.7 0 3.2.6 4.4 1.7l3.3-3.2A11.5 11.5 0 0 0 1.8 6.8l3.8 3c.9-2.7 3.4-4.4 6.4-4.4Z" />
              </svg>
              Sign in with Google
            </button>

            {notice && <p className="text-center text-xs text-slate-500">{notice}</p>}
          </form>

          <p className="mt-7 text-center text-sm text-slate-600">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="font-medium text-brand-600 hover:text-brand-700">
              Sign up
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
