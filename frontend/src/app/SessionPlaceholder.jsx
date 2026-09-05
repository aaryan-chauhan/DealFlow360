import { useMeQuery } from '../auth/authApi'

/** Phase-1 landing page: proves the JWT session works. The real Dashboard is a later phase. */
export default function SessionPlaceholder() {
  const { data, isLoading } = useMeQuery()
  const membership = data?.active_membership

  return (
    <div className="max-w-md rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-lg font-semibold text-slate-900">Signed in</h1>
      <p className="mt-1 text-sm text-slate-500">
        Authenticated against the Django API. The Dashboard screen arrives in a later phase — use
        the sidebar for the screens built so far.
      </p>

      {isLoading ? (
        <p className="mt-6 text-sm text-slate-500">Loading session…</p>
      ) : (
        <dl className="mt-6 space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Email</dt>
            <dd className="font-medium text-slate-900">{data?.user?.email}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Company</dt>
            <dd className="font-medium text-slate-900">{membership?.company?.name ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Role</dt>
            <dd className="font-medium text-slate-900">{membership?.role?.label ?? '—'}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}
