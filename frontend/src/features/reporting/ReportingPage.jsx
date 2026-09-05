import { useState } from 'react'
import { useSelector } from 'react-redux'

import { selectAccessToken } from '../../auth/authSlice'
import { useGetProductsQuery } from '../admin/catalogApi'
import { downloadReport, useGetReportingSummaryQuery } from './reportingApi'

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'This Week' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
  { value: 'all', label: 'All Time' },
  { value: 'custom', label: 'Custom Range' },
]

// Mirrors catalog.Product.CATEGORY_CHOICES (backend/catalog/models.py) — kept as a
// literal list rather than a live lookup since these four are fixed enum values.
const CATEGORIES = ['Hardware', 'Software', 'Services', 'Subscription']

const APPROVAL_STATUSES = [
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'negotiation', label: 'Negotiation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
]

export default function ReportingPage() {
  const token = useSelector(selectAccessToken)
  const [period, setPeriod] = useState('30d')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [salesRep, setSalesRep] = useState('')
  const [approvalStatus, setApprovalStatus] = useState('')
  const [category, setCategory] = useState('')
  const [product, setProduct] = useState('')
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  const filters = {
    period,
    date_from: period === 'custom' ? dateFrom || undefined : undefined,
    date_to: period === 'custom' ? dateTo || undefined : undefined,
    sales_rep: salesRep || undefined,
    approval_status: approvalStatus || undefined,
    category: category || undefined,
    product: product || undefined,
  }

  const { data, isLoading } = useGetReportingSummaryQuery(filters)
  // Fetched unfiltered by rep so the rep dropdown always lists everyone with report
  // activity, even while a rep filter narrows the summary itself.
  const { data: unfilteredData } = useGetReportingSummaryQuery({})
  const { data: products = [] } = useGetProductsQuery()

  async function handleExport(format) {
    setExportError('')
    setIsExporting(true)
    try {
      await downloadReport(token, { format, ...filters })
    } catch {
      setExportError(`Failed to export ${format.toUpperCase()} report.`)
    } finally {
      setIsExporting(false)
    }
  }

  const summary = data?.summary || {}
  const topSkus = data?.top_skus || []
  const leaderboard = data?.rep_leaderboard || []
  const repOptions = unfilteredData?.rep_leaderboard || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Reporting & Analytics Dashboard</h1>
          <p className="text-xs text-slate-500">
            Executive sales KPIs, margin distributions, top selling products, and PDF/XLS export (§7.5)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('xls')}
            disabled={isExporting}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 shadow transition disabled:opacity-50"
          >
            {isExporting ? 'Exporting…' : 'Export XLS'}
          </button>
          <button
            onClick={() => handleExport('pdf')}
            disabled={isExporting}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 shadow transition disabled:opacity-50"
          >
            {isExporting ? 'Exporting…' : 'Export PDF'}
          </button>
        </div>
      </div>

      {exportError && (
        <div className="rounded-xl bg-rose-50 border border-rose-200 p-3.5 text-xs text-rose-800 font-medium">
          {exportError}
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Period
          </label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {period === 'custom' && (
          <>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                From
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                To
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
              />
            </div>
          </>
        )}

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Sales Rep
          </label>
          <select
            value={salesRep}
            onChange={(e) => setSalesRep(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            <option value="">All Reps</option>
            {repOptions.map((r) => (
              <option key={r.rep_id} value={r.rep_id}>{r.rep_name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Approval Status
          </label>
          <select
            value={approvalStatus}
            onChange={(e) => setApprovalStatus(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            <option value="">All Statuses</option>
            {APPROVAL_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Category
          </label>
          <select
            value={category}
            onChange={(e) => { setCategory(e.target.value); setProduct('') }}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Product
          </label>
          <select
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            <option value="">All Products</option>
            {products
              .filter((p) => !category || p.category === category)
              .map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Calculating aggregate performance analytics...
        </div>
      ) : (
        <>
          {/* Executive KPI Grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Confirmed Revenue</p>
              <div className="mt-2 text-2xl font-bold text-slate-900">
                ₹{(summary.total_revenue || 0).toLocaleString('en-IN')}
              </div>
              <p className="mt-1 text-[11px] font-medium text-emerald-600">
                {summary.confirmed_count || 0} Confirmed Orders
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Pipeline Value</p>
              <div className="mt-2 text-2xl font-bold text-slate-900">
                ₹{(summary.pipeline_value || 0).toLocaleString('en-IN')}
              </div>
              <p className="mt-1 text-[11px] font-medium text-indigo-600">
                {summary.total_quotations_count || 0} Total Quotes
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Win Rate %</p>
              <div className="mt-2 text-2xl font-bold text-brand-600">
                {summary.win_rate_pct || 0}%
              </div>
              <p className="mt-1 text-[11px] font-medium text-slate-500">Proposal Conversion Rate</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Average Gross Margin</p>
              <div className="mt-2 text-2xl font-bold text-emerald-600">
                {summary.avg_margin_pct || 0}%
              </div>
              <p className="mt-1 text-[11px] font-medium text-slate-500">Margin Guardrail Target</p>
            </div>
          </div>

          {/* Tables Section: Top Products & Rep Leaderboard */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Top Selling Products */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900">Top Selling Products</h3>
                <span className="text-xs text-slate-400">By Revenue</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Product Name</th>
                      <th className="px-3 py-2 text-right">Units Sold</th>
                      <th className="px-3 py-2 text-right">Total Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {topSkus.length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-3 py-4 text-center text-slate-400">
                          No product sales recorded yet.
                        </td>
                      </tr>
                    )}
                    {topSkus.map((sku) => (
                      <tr key={sku.sku} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5 font-semibold text-slate-900">{sku.product_name}</td>
                        <td className="px-3 py-2.5 text-right font-medium text-slate-800">{sku.quantity}</td>
                        <td className="px-3 py-2.5 text-right font-bold text-brand-600">
                          ₹{sku.sales_amount.toLocaleString('en-IN')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sales Rep Leaderboard */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900">Sales Rep Leaderboard</h3>
                <span className="text-xs text-slate-400">Pipeline Performance</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Sales Representative</th>
                      <th className="px-3 py-2 text-center">Quotes Created</th>
                      <th className="px-3 py-2 text-right">Total Deal Volume</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {leaderboard.length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-3 py-4 text-center text-slate-400">
                          No sales rep activity recorded.
                        </td>
                      </tr>
                    )}
                    {leaderboard.map((rep) => (
                      <tr key={rep.rep_id} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5 font-semibold text-slate-900">{rep.rep_name}</td>
                        <td className="px-3 py-2.5 text-center font-medium text-slate-700">{rep.quote_count}</td>
                        <td className="px-3 py-2.5 text-right font-bold text-slate-900">
                          ₹{rep.total_value.toLocaleString('en-IN')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
