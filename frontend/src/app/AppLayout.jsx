import { useDispatch, useSelector } from 'react-redux'
import { NavLink, Outlet } from 'react-router-dom'

import { useLogoutMutation } from '../auth/authApi'
import { loggedOut, selectActiveMembership, selectCurrentUser, selectRefreshToken } from '../auth/authSlice'
import Logo from '../shared/ui/Logo'

const icons = {
  dashboard: 'M4 13h7V4H4v9Zm0 7h7v-5H4v5Zm9 0h7v-9h-7v9Zm0-16v5h7V4h-7Z',
  quotations: 'M6 3h9l4 4v14H6V3Zm8 0v5h5M9 12h7M9 16h7',
  customers: 'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3 20c0-2.8 2.2-5 5-5s5 2.2 5 5m3-5c2.8 0 5 2.2 5 5',
  products: 'M12 3 3 7.5 12 12l9-4.5L12 3ZM3 12l9 4.5L21 12M3 16.5 12 21l9-4.5',
  discounts: 'M9 15 15 9M9.5 9.5h.01M14.5 14.5h.01M4 4h16v16H4z',
  orders: 'M3 6h18M3 12h18M3 18h18',
  invoices: 'M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6M9 12h6',
  subscriptions: 'M4 12a8 8 0 0 1 13.7-5.7M20 12a8 8 0 0 1-13.7 5.7M18 4v4h-4M6 20v-4h4',
  reports: 'M4 20V10m5 10V4m5 16v-7m5 7V8',
  settings:
    'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8-3a8 8 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a8 8 0 0 0-2-1.2L15 3H9l-.5 2.6a8 8 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5a8 8 0 0 0 0 2.4l-2 1.5 2 3.5 2.4-1a8 8 0 0 0 2 1.2L9 21h6l.5-2.6a8 8 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5A8 8 0 0 0 20 12Z',
}

// Nav mirrors the wireframe; only the screens built so far are live. Later phases
// switch these on one at a time.
const NAV = [
  { label: 'Dashboard', to: '/dashboard', icon: 'dashboard' },
  { label: 'Deal Health', to: '/deal-health', icon: 'reports' },
  { label: 'Reports', to: '/reports', icon: 'reports', roles: ['sales_manager', 'admin'] },
  { label: 'Quotations', to: '/quotations', icon: 'quotations' },
  {
    label: 'Approvals',
    to: '/approvals',
    icon: 'discounts',
    roles: ['sales_manager', 'finance_ops', 'admin'],
  },
  {
    label: 'Fulfillment',
    to: '/fulfillment',
    icon: 'orders',
    roles: ['finance_ops', 'admin', 'sales_manager'],
  },
  {
    label: 'Warehouses',
    to: '/admin/warehouses',
    icon: 'orders',
    roles: ['admin', 'finance_ops', 'sales_manager'],
  },
  { label: 'Products', to: '/admin/products', icon: 'products', roles: ['admin'] },
  {
    label: 'Discount Config',
    to: '/admin/discount-config',
    icon: 'discounts',
    roles: ['admin', 'sales_manager'],
  },
  { label: 'Invoices', to: '/invoices', icon: 'invoices' },

  { label: 'Subscriptions', to: '/subscriptions', icon: 'subscriptions' },
]


function NavIcon({ name }) {
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={icons[name]} />
    </svg>
  )
}

export default function AppLayout() {
  const user = useSelector(selectCurrentUser)
  const membership = useSelector(selectActiveMembership)
  const refresh = useSelector(selectRefreshToken)
  const [logout] = useLogoutMutation()
  const dispatch = useDispatch()

  const role = membership?.role?.code
  const initials = (user?.full_name || user?.email || '?')
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  async function handleLogout() {
    try {
      await logout({ refresh }).unwrap()
    } catch {
      /* token may already be expired — clear locally regardless */
    }
    dispatch(loggedOut())
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 flex w-56 flex-col bg-ink-900">
        <div className="px-5 py-5">
          <Logo />
        </div>
        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.filter((item) => !item.roles || item.roles.includes(role)).map((item) => {
            return (
              <NavLink
                key={item.label}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    isActive
                      ? 'bg-brand-600 font-medium text-white'
                      : 'text-slate-300 hover:bg-ink-700 hover:text-white'
                  }`
                }
              >
                <NavIcon name={item.icon} />
                {item.label}
              </NavLink>
            )
          })}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col pl-56">
        <header className="sticky top-0 z-30 flex items-center gap-4 border-b border-slate-200 bg-white px-6 py-3">
          <div className="relative max-w-xs flex-1">
            <svg viewBox="0 0 24 24" className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
            <input
              placeholder="Search..."
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-9 pr-3 text-sm outline-none focus:border-brand-600 focus:bg-white"
            />
          </div>

          <div className="ml-auto flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
              {initials}
            </span>
            <div className="leading-tight">
              <p className="text-sm font-medium text-slate-900">{user?.full_name || user?.email}</p>
              <p className="text-xs text-slate-500">{membership?.role?.label ?? '—'}</p>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Log out
            </button>
          </div>
        </header>

        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
