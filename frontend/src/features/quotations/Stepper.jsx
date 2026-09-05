export const STEPS = ['Customer', 'Products', 'Review', 'Submit']

export default function Stepper({ current }) {
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {STEPS.map((label, index) => {
        const state = index < current ? 'done' : index === current ? 'active' : 'todo'
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm ${
                state === 'active'
                  ? 'bg-brand-50 font-medium text-brand-700'
                  : state === 'done'
                    ? 'text-emerald-700'
                    : 'text-slate-400'
              }`}
            >
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold ${
                  state === 'active'
                    ? 'bg-brand-600 text-white'
                    : state === 'done'
                      ? 'bg-emerald-500 text-white'
                      : 'border border-slate-300 text-slate-400'
                }`}
              >
                {state === 'done' ? '✓' : index + 1}
              </span>
              {label}
            </span>
            {index < STEPS.length - 1 && <span className="h-px w-8 bg-slate-200" />}
          </li>
        )
      })}
    </ol>
  )
}
