import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useEscalateAlertMutation,
  useGetAlertsQuery,
  useNudgeAlertMutation,
  useTriggerScanMutation,
} from './dealHealthApi'

export default function DealHealthPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [escalateModalAlert, setEscalateModalAlert] = useState(null)
  const [escalationNote, setEscalationNote] = useState('')
  const [scanMessage, setScanMessage] = useState('')

  const { data: alerts = [], isLoading, refetch } = useGetAlertsQuery({
    status: statusFilter || undefined,
    severity: severityFilter || undefined,
  })

  const [triggerScan, { isLoading: isScanning }] = useTriggerScanMutation()
  const [escalateAlert, { isLoading: isEscalating }] = useEscalateAlertMutation()
  const [nudgeAlert] = useNudgeAlertMutation()

  async function handleScan() {
    setScanMessage('')
    try {
      const res = await triggerScan().unwrap()
      setScanMessage(`Scan complete: ${res.scanned_count} checked, ${res.new_alerts_count} new alert(s) generated.`)
      refetch()
    } catch {
      setScanMessage('Failed to complete scan.')
    }
  }

  async function handleEscalateSubmit(e) {
    e.preventDefault()
    if (!escalateModalAlert) return
    try {
      await escalateAlert({ id: escalateModalAlert.id, note: escalationNote }).unwrap()
      setEscalateModalAlert(null)
      setEscalationNote('')
    } catch {
      alert('Failed to escalate alert.')
    }
  }

  async function handleNudge(alertId) {
    try {
      await nudgeAlert(alertId).unwrap()
    } catch {
      alert('Failed to nudge quote owner.')
    }
  }

  // Summary Metrics
  const openCount = alerts.filter((a) => a.status === 'Open').length
  const criticalCount = alerts.filter((a) => a.severity === 'Critical' || a.severity === 'High').length
  const totalStalledVal = alerts
    .filter((a) => a.alert_type === 'stalled_deal' && a.total_amount)
    .reduce((sum, a) => sum + parseFloat(a.total_amount || 0), 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Deal Health & Anomaly Scanner</h1>
          <p className="text-xs text-slate-500">
            Real-time pipeline scanner detecting stalled deals, discount baseline anomalies, and delivery slippages (§7.3)
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 shadow transition disabled:opacity-50"
        >
          {isScanning ? (
            <>
              <svg className="h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Scanning Pipeline...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Run Instant Scan
            </>
          )}
        </button>
      </div>

      {scanMessage && (
        <div className="rounded-xl bg-indigo-50 border border-indigo-200 p-3.5 text-xs text-indigo-800 font-medium">
          {scanMessage}
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Active Alerts</p>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-slate-900">{alerts.length}</span>
            <span className="text-xs font-medium text-slate-500">{openCount} unhandled</span>
          </div>
        </div>

        <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-rose-600">High & Critical Risk</p>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-rose-700">{criticalCount}</span>
            <span className="text-xs font-medium text-rose-600">Requires Action</span>
          </div>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">Stalled Quote Value</p>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-amber-800">₹{totalStalledVal.toLocaleString('en-IN')}</span>
            <span className="text-xs font-medium text-amber-600">Pipeline Exposure</span>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Filters:</span>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
        >
          <option value="">All Statuses</option>
          <option value="Open">Open</option>
          <option value="Escalated">Escalated</option>
          <option value="Nudged">Nudged</option>
          <option value="Resolved">Resolved</option>
        </select>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-brand-600 focus:bg-white"
        >
          <option value="">All Severities</option>
          <option value="Critical">Critical</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
      </div>

      {/* Alerts Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {isLoading ? (
          <p className="text-sm text-slate-500">Loading deal health alerts...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Alert Title & Type</th>
                  <th className="px-4 py-3">Customer / Quote</th>
                  <th className="px-4 py-3">Recommended Action</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {alerts.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-xs text-slate-500">
                      No anomaly alerts found for the selected filters. All active deals are healthy!
                    </td>
                  </tr>
                )}
                {alerts.map((alert) => {
                  const severityBadge =
                    alert.severity === 'Critical'
                      ? 'bg-rose-100 text-rose-800 border-rose-200'
                      : alert.severity === 'High'
                      ? 'bg-amber-100 text-amber-800 border-amber-200'
                      : 'bg-slate-100 text-slate-700 border-slate-200'

                  const statusBadge =
                    alert.status === 'Escalated'
                      ? 'bg-purple-100 text-purple-800'
                      : alert.status === 'Nudged'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-emerald-100 text-emerald-800'

                  return (
                    <tr key={alert.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-semibold ${severityBadge}`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{alert.title}</div>
                        <div className="text-xs text-slate-500 line-clamp-1">{alert.description}</div>
                      </td>
                      <td className="px-4 py-3">
                        {alert.quotation_number ? (
                          <div>
                            <div className="font-medium text-slate-800">{alert.customer_name || 'Customer'}</div>
                            <Link
                              to={`/quotations/${alert.quotation}`}
                              className="text-xs font-semibold text-brand-600 hover:underline"
                            >
                              {alert.quotation_number}
                            </Link>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">N/A</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600 max-w-xs">
                        {alert.recommended_action || 'Review and take action'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${statusBadge}`}>
                          {alert.status}
                        </span>
                        {alert.nudge_count > 0 && (
                          <div className="text-[10px] text-slate-400">Nudged x{alert.nudge_count}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => handleNudge(alert.id)}
                          title="Send nudge reminder to quote owner"
                          className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 transition"
                        >
                          🔔 Nudge
                        </button>
                        <button
                          onClick={() => setEscalateModalAlert(alert)}
                          className="rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100 transition border border-rose-200"
                        >
                          ⚠️ Escalate
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Escalation Modal */}
      {escalateModalAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <form
            onSubmit={handleEscalateSubmit}
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4"
          >
            <h3 className="text-lg font-bold text-slate-900">Escalate Deal Anomaly</h3>
            <p className="text-xs text-slate-500">
              Escalating alert for <strong className="text-slate-800">{escalateModalAlert.title}</strong> to Sales Operations & Leadership.
            </p>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Escalation Note</label>
              <textarea
                rows={3}
                required
                placeholder="Reason for escalation or additional context..."
                value={escalationNote}
                onChange={(e) => setEscalationNote(e.target.value)}
                className="w-full rounded-xl border border-slate-200 p-3 text-sm outline-none focus:border-brand-600"
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setEscalateModalAlert(null)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isEscalating}
                className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 shadow"
              >
                Confirm Escalation
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
