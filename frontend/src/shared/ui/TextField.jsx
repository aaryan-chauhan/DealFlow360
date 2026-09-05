import { useState } from 'react'

export default function TextField({ label, type = 'text', error, ...props }) {
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'

  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      <div className="relative">
        <input
          {...props}
          type={isPassword && revealed ? 'text' : type}
          className={`w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:ring-4 ${
            error
              ? 'border-red-400 focus:border-red-500 focus:ring-red-100'
              : 'border-slate-300 focus:border-brand-600 focus:ring-brand-100'
          } ${isPassword ? 'pr-11' : ''}`}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed((v) => !v)}
            aria-label={revealed ? 'Hide password' : 'Show password'}
            className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-400 hover:text-slate-600"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path
                d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="12" cy="12" r="3" />
              {!revealed && <path d="m4 4 16 16" strokeLinecap="round" />}
            </svg>
          </button>
        )}
      </div>
      {error && <span className="mt-1.5 block text-xs text-red-600">{error}</span>}
    </label>
  )
}
