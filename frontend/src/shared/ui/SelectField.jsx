export default function SelectField({ label, options, error, ...props }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      <select
        {...props}
        className={`w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:ring-4 ${
          error
            ? 'border-red-400 focus:border-red-500 focus:ring-red-100'
            : 'border-slate-300 focus:border-brand-600 focus:ring-brand-100'
        }`}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <span className="mt-1.5 block text-xs text-red-600">{error}</span>}
    </label>
  )
}
