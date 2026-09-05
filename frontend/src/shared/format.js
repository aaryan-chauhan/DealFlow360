export function formatCurrency(value, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value ?? 0))
}

/** "5.00" -> "5%", "12.50" -> "12.5%" */
export function formatPct(value) {
  return `${parseFloat(value ?? 0)}%`
}
