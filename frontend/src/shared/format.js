// INR is the one currency here whose grouping actually differs (lakhs/crores) from
// plain thousands, which is why it gets its own locale — every other supported currency
// (backend `PriceList.CURRENCY_CHOICES`) renders correctly off a single Western locale,
// since `Intl.NumberFormat` picks the right symbol from `currency` regardless of locale.
const LOCALE_BY_CURRENCY = { INR: 'en-IN' }

export function formatCurrency(value, currency = 'INR') {
  const locale = LOCALE_BY_CURRENCY[currency] || 'en-US'
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value ?? 0))
}

/** "5.00" -> "5%", "12.50" -> "12.5%" */
export function formatPct(value) {
  return `${parseFloat(value ?? 0)}%`
}
