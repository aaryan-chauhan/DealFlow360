const TONES = {
  draft: 'bg-slate-100 text-slate-600',
  pending_approval: 'bg-amber-100 text-amber-700',
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-emerald-100 text-emerald-700',
  negotiation: 'bg-violet-100 text-violet-700',
  confirmed: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-700',
  returned: 'bg-orange-100 text-orange-700',
  superseded: 'bg-slate-100 text-slate-500',
  suggested: 'bg-sky-100 text-sky-700',
  accepted: 'bg-emerald-100 text-emerald-700',
  backordered: 'bg-red-100 text-red-700',
  fulfilled: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-slate-100 text-slate-500',
  Gold: 'bg-amber-100 text-amber-700',
  Silver: 'bg-slate-200 text-slate-700',
  Bronze: 'bg-orange-100 text-orange-700',
}

const LABELS = {
  draft: 'Draft',
  pending_approval: 'Pending Approval',
  pending: 'Pending',
  approved: 'Approved',
  negotiation: 'Negotiation',
  confirmed: 'Confirmed',
  rejected: 'Rejected',
  returned: 'Returned',
  superseded: 'Superseded',
  suggested: 'Split Suggested',
  accepted: 'Split Accepted',
  backordered: 'Partially Backordered',
  fulfilled: 'Fulfilled',
  cancelled: 'Cancelled',
}

export default function StatusPill({ value, label }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${
        TONES[value] ?? 'bg-slate-100 text-slate-600'
      }`}
    >
      {label ?? LABELS[value] ?? value}
    </span>
  )
}
