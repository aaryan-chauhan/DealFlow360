export default function Logo({ className = '' }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white shadow-lg shadow-brand-600/30">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M4 17.5 9.5 12l3.5 3.5L20 8" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M15 8h5v5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="text-2xl font-semibold tracking-tight text-white">
        DealFlow<span className="text-brand-500">360</span>
      </span>
    </div>
  )
}
