import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { parseApiError } from '../../shared/api/errors'
import CustomerStep from './CustomerStep'
import ProductsStep from './ProductsStep'
import ReviewStep from './ReviewStep'
import Stepper from './Stepper'
import {
  useCreateQuotationMutation,
  useGetQuotationQuery,
  useSubmitForApprovalMutation,
} from './quotationsApi'

function SubmitOutcome({ result, quotation }) {
  const routed = result.approval_request
  const assessment = result.assessment
  return (
    <div className="space-y-4">
      <div
        className={`rounded-xl border p-5 ${
          routed ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'
        }`}
      >
        <h2 className={`text-base font-semibold ${routed ? 'text-amber-900' : 'text-emerald-900'}`}>
          {routed
            ? 'Submitted — approval required'
            : 'Approved automatically — no review needed'}
        </h2>
        <p className={`mt-1 text-sm ${routed ? 'text-amber-800' : 'text-emerald-800'}`}>
          {quotation.number} · routing score {parseFloat(assessment.routing_score)} (blended{' '}
          {parseFloat(assessment.blended_score)}, worst single line{' '}
          {parseFloat(assessment.max_single_overage)} pts over its ceiling).
        </p>
        {routed && (
          <p className="mt-2 text-sm text-amber-800">
            Routed to{' '}
            <strong>
              {routed.required_level === 'manager_then_finance'
                ? 'Sales Manager → Finance'
                : 'Sales Manager'}
            </strong>
            .{' '}
            <Link to={`/approvals/${routed.id}`} className="font-medium underline">
              Open approval
            </Link>
          </p>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Line</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Discount</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Ceiling</th>
              <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">Over by</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {assessment.lines.map((line) => {
              const quoteLine = quotation.lines.find((l) => l.id === line.line_id)
              const over = parseFloat(line.overage_pct) > 0
              return (
                <tr key={line.line_id} className={over ? 'bg-red-50' : ''}>
                  <td className="px-5 py-2.5 text-sm text-slate-900">
                    {quoteLine?.product_name ?? line.category}
                  </td>
                  <td className="px-5 py-2.5 text-right text-sm text-slate-700">
                    {parseFloat(line.discount_pct)}%
                  </td>
                  <td className="px-5 py-2.5 text-right text-sm text-slate-500">
                    {parseFloat(line.ceiling_pct)}%
                  </td>
                  <td
                    className={`px-5 py-2.5 text-right text-sm font-medium ${
                      over ? 'text-red-700' : 'text-slate-400'
                    }`}
                  >
                    {over ? `+${parseFloat(line.overage_pct)}` : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end gap-2">
        <Link
          to="/quotations"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back to Quotations
        </Link>
      </div>
    </div>
  )
}

function Builder({ id }) {
  const navigate = useNavigate()
  const isNew = !id

  const [step, setStep] = useState(isNew ? 0 : 2)
  const landed = useRef(false)
  const [customer, setCustomer] = useState(null)
  const [submitResult, setSubmitResult] = useState(null)

  const { data: quotation, isLoading } = useGetQuotationQuery(id, { skip: isNew })
  const [createQuotation, { isLoading: isCreating, error: createError }] =
    useCreateQuotationMutation()
  const [submitForApproval, { isLoading: isSubmitting, error: submitError }] =
    useSubmitForApprovalMutation()

  const { formError: createFormError } = parseApiError(createError)

  // An empty draft has nothing to review — land the rep on the product picker instead.
  useEffect(() => {
    if (landed.current || !quotation) return
    landed.current = true
    if (quotation.status === 'draft' && quotation.lines.length === 0) setStep(1)
  }, [quotation])

  async function handleContinueFromCustomer() {
    if (!customer) return
    try {
      const created = await createQuotation({ customer: customer.id }).unwrap()
      navigate(`/quotations/${created.id}`, { replace: true })
    } catch {
      /* surfaced through `createError` */
    }
  }

  async function handleSubmit() {
    try {
      const result = await submitForApproval(quotation.id).unwrap()
      setSubmitResult(result)
      setStep(3)
    } catch {
      /* surfaced through `submitError` */
    }
  }

  if (!isNew && isLoading) {
    return <p className="text-sm text-slate-500">Loading quotation…</p>
  }

  const editable = quotation?.can_edit ?? true

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {isNew ? 'Create Quotation' : quotation.number}
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {isNew
              ? 'Pick a customer, build the cart, then submit for governance review.'
              : `${quotation.customer_name} · owned by ${quotation.owner_name}`}
          </p>
        </div>
        <Link to="/quotations" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          All quotations
        </Link>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <Stepper current={step} />
      </div>

      {step === 0 && (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <CustomerStep
            selectedId={customer?.id}
            onSelect={setCustomer}
            error={createFormError}
          />
          <div className="flex justify-end">
            <button
              onClick={handleContinueFromCustomer}
              disabled={!customer || isCreating}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {isCreating ? 'Creating…' : 'Continue'}
            </button>
          </div>
        </div>
      )}

      {step === 1 && quotation && (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <ProductsStep quotationId={quotation.id} lines={quotation.lines} />
          <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
            <button
              onClick={() => setStep(2)}
              disabled={quotation.lines.length === 0}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              Continue to Review
            </button>
          </div>
        </div>
      )}

      {step === 2 && quotation && (
        <ReviewStep
          quotation={quotation}
          editable={editable}
          onBack={editable ? () => setStep(1) : undefined}
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
          submitError={submitError}
        />
      )}

      {step === 3 && submitResult && (
        <SubmitOutcome result={submitResult} quotation={submitResult.quotation} />
      )}
    </div>
  )
}

/** Keyed on the route so moving between "new" and an existing quote remounts the wizard
 *  instead of leaving it stuck on the previous quote's step. */
export default function QuotationBuilderPage() {
  const { id } = useParams()
  return <Builder key={id ?? 'new'} id={id} />
}
