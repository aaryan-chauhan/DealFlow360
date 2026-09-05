import { useState } from 'react'
import { useGetReportingSummaryQuery } from './reportingApi'

export default function ReportingPage() {
  const [dateRange, setDateRange] = useState('30d')
  const [salesRep, setSalesRep] = useState('')

  const { data, isLoading } = useGetReportingSummaryQuery({
    date_range: dateRange,
    sales_rep: salesRep || undefined,
  })

  function handleExportCSV() {
    const token = localStorage.getItem('token')
    const url = `/api/reports/export?sales_rep=${encodeURIComponent(salesRep)}`
    
    // Create an anchor tag to trigger download with auth
    fetch(url, {
      headers: {
        Authorization: token ? `Bearer ${token}` : '',
      },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const downloadUrl = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = downloadUrl
        a.download = 'dealflow_sales_report.csv'
        document.body.appendChild(a)
        a.click()
        a.remove()
      })
      .catch(() => alert('Failed to download report export.'))
  }

  const summary = data?.summary || {}
  const topSkus = data?.top_skus || []
  const leaderboard = data?.rep_leaderboard || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Reporting & Analytics Dashboard</h1>
          <p className="text-xs text-slate-500">
            Executive sales KPIs, margin distributions, top selling products, and CSV data export (§7.5)
          </p>
        </div>

        <button
          onClick={handleExportCSV}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 shadow transition"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Export CSV Report
        </button>
      </div>

      {/* Toolbar Filter */}
      <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Date Range:</span>
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="all">All Time</option>
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

          {/* Tables Section: Top SKUs & Rep Leaderboard */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Top Selling Products */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900">Top Selling SKUs</h3>
                <span className="text-xs text-slate-400">By Revenue</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Product Name</th>
                      <th className="px-3 py-2">SKU</th>
                      <th className="px-3 py-2 text-right">Units Sold</th>
                      <th className="px-3 py-2 text-right">Total Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {topSkus.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                          No product sales recorded yet.
                        </td>
                      </tr>
                    )}
                    {topSkus.map((sku, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5 font-semibold text-slate-900">{sku.product_name}</td>
                        <td className="px-3 py-2.5 text-slate-500 font-mono">{sku.sku}</td>
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
                    {leaderboard.map((rep, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
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
